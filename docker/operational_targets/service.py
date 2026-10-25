"""Disposable business service, lifecycle controller and independent observer.

Both HTTP listeners bind only container loopback. No shell, path or arbitrary
command is accepted. The observer reads the business endpoint independently
of the controller's recovery response. This file has no ARYN credentials.
"""

import argparse
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def request(port, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data,
        headers={"Content-Type": "application/json"})
    try:
        response = urllib.request.urlopen(req, timeout=2)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        raw = response.read(8193)
        if len(raw) > 8192:
            raise ValueError("Response exceeds limit.")
        return response.status, json.loads(raw)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, status, value):
        raw = json.dumps(value, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path != "/health":
            return self.reply(404, {"error": "unknown_endpoint"})
        if self.server.worker:
            with self.server.lock:
                self.server.requests += 1
            healthy = not self.server.fault
            return self.reply(200 if healthy else 503, {
                "instance": self.server.instance, "healthy": healthy,
                "requests": self.server.requests,
            })
        with self.server.lock:
            self.reply(200, self.server.snapshot())

    def do_POST(self):
        if self.server.worker or self.path != "/control":
            return self.reply(404, {"error": "unknown_endpoint"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 1 <= length <= 4096:
                raise ValueError("Body exceeds limit.")
            data = json.loads(self.rfile.read(length))
            with self.server.lock:
                result = self.server.control(data)
            self.reply(200, result)
        except (ValueError, TypeError, KeyError):
            self.reply(409, {"error": "invalid_or_stale_control"})


class Service(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, *, worker=False, instance=None, fault=False, ttl=3600):
        super().__init__(("127.0.0.1", 8081 if worker else 8080), Handler)
        self.worker, self.fault, self.requests = worker, fault, 0
        self.instance = instance or uuid.uuid4().hex
        self.generation, self.child, self.last_execution = 1, None, None
        self.child_instance = uuid.uuid4().hex
        self.lock = threading.Lock()
        self.deadline = time.time() + ttl
        if not worker:
            self.start_child(self.child_instance)

    def start_child(self, identity):
        self.child = subprocess.Popen([sys.executable, "-B", os.path.abspath(__file__),
            "worker", "--instance", identity, "--ttl", str(max(30, math.ceil(self.deadline - time.time()))),
            *(["--fault"] if self.fault else [])],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.child_instance = identity

    def snapshot(self):
        return {"instance": self.instance, "generation": self.generation,
            "running": self.child is not None and self.child.poll() is None,
            "blocking_fault": self.fault, "child_instance": self.child_instance,
            "last_execution_id": self.last_execution, "expires_at": self.deadline}

    def stop_child(self):
        if self.child is not None and self.child.poll() is None:
            self.child.terminate()
            try:
                self.child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.child.kill()
                self.child.wait(timeout=2)

    def control(self, data):
        action = data.get("action")
        if action in {"stop_worker", "latch_unhealthy"}:
            if set(data) != {"action"}:
                raise ValueError("Fault injection accepts no parameters.")
            self.stop_child()
            self.fault = action == "latch_unhealthy"
            self.generation += 1
            self.last_execution = None
            return self.snapshot()
        if set(data) != {"action", "instance", "generation", "execution_id", "deadline_at"}:
            raise ValueError("Recovery contract differs.")
        if (action != "restart_service" or data["instance"] != self.instance
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", data["execution_id"])
                or type(data["generation"]) is not int
                or type(data["deadline_at"]) not in {float, int}
                or not time.time() < data["deadline_at"] <= self.deadline):
            raise ValueError("Recovery identity or deadline differs.")
        if self.last_execution == data["execution_id"]:
            if self.generation != data["generation"] + 1:
                raise ValueError("Execution checkpoint differs.")
            return self.snapshot()
        if data["generation"] != self.generation or self.snapshot()["running"]:
            raise ValueError("Recovery target is no longer stopped at that generation.")
        self.stop_child()
        self.start_child(data["execution_id"])
        self.generation += 1
        self.last_execution = data["execution_id"]
        return self.snapshot()


def observe():
    started = time.monotonic()
    controller_status, controller = request(8080, "/health")
    try:
        status, business = request(8081, "/health")
        available = True
    except (OSError, ValueError):
        status, business, available = None, None, False
    return {"controller_status": controller_status, "controller": controller,
        "business_status": status, "business": business, "business_available": available,
        "healthy": bool(available and status == 200 and business.get("healthy") is True
            and controller["running"] and business.get("instance") == controller["child_instance"]),
        "observed_at": time.time(), "latency_ms": round((time.monotonic() - started) * 1000, 3)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["serve", "worker", "observe", "control"])
    parser.add_argument("--instance")
    parser.add_argument("--fault", action="store_true")
    parser.add_argument("--ttl", type=int, default=3600)
    args = parser.parse_args()
    if args.mode == "observe":
        print(json.dumps(observe(), separators=(",", ":")))
        return
    if args.mode == "control":
        raw = sys.stdin.buffer.read(4097)
        if len(raw) > 4096:
            raise ValueError("Control input exceeds limit.")
        status, result = request(8080, "/control", json.loads(raw))
        if status != 200:
            raise ValueError("Control rejected.")
        print(json.dumps(result, separators=(",", ":")))
        return
    if not 30 <= args.ttl <= 28800:
        raise ValueError("Lifetime must be bounded.")
    service = Service(worker=args.mode == "worker", instance=args.instance,
        fault=args.fault, ttl=args.ttl)
    service.timeout = 0.25
    try:
        while time.time() < service.deadline:
            service.handle_request()
    finally:
        service.stop_child()
        service.server_close()


if __name__ == "__main__":
    main()
