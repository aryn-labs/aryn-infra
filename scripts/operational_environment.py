"""Trusted local lifecycle CLI; no ports, credentials or user-data mounts."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import uuid

PROFILE = {"network": "none", "read_only_root": True, "user": "65532:65532",
    "memory_bytes": 134217728, "nano_cpus": 500000000, "pids": 64}


def docker(*args, data=None, timeout=30):
    environment = dict(os.environ)
    if args[0] == "build":
        # The classic local builder consumes the already verified image ID;
        # BuildKit treats an unqualified sha256 ID as a registry repository.
        environment["DOCKER_BUILDKIT"] = "0"
    result = subprocess.run(["docker", *args], input=data, capture_output=True,
        timeout=timeout, env=environment)
    if result.returncode or len(result.stdout) > 65536:
        raise RuntimeError("Owned environment Docker operation failed.")
    return result.stdout.decode().strip()


def owned(binding):
    inspected = json.loads(docker("inspect", binding["container_id"]))[0]
    host, config = inspected["HostConfig"], inspected["Config"]
    if (inspected["Id"] != binding["container_id"] or inspected["Image"] != binding["image_id"]
            or config["Labels"].get("aryn.operational.environment") != binding["environment_id"]
            or config["Labels"].get("aryn.organization") != binding["organization_id"]
            or config["Labels"].get("aryn.project") != binding["project_id"]
            or host["NetworkMode"] != "none" or not host["ReadonlyRootfs"]
            or config["User"] != PROFILE["user"] or host["Privileged"]
            or host.get("Binds") or host.get("Tmpfs") or host.get("PublishAllPorts")
            or host.get("UsernsMode") == "host" or set(inspected["NetworkSettings"]["Networks"]) != {"none"}
            or inspected["Mounts"] or host["PortBindings"]
            or host["Memory"] != PROFILE["memory_bytes"]
            or host["MemorySwap"] != PROFILE["memory_bytes"] or host["Devices"]
            or host["PidMode"] == "host" or host["IpcMode"] == "host"
            or host["NanoCpus"] != PROFILE["nano_cpus"] or host["PidsLimit"] != PROFILE["pids"]
            or host["CapDrop"] != ["ALL"] or host["CapAdd"]
            or "no-new-privileges" not in host["SecurityOpt"]):
        raise RuntimeError("Owned target isolation identity differs.")


def build_record(path):
    return path.with_name(path.stem + "-build.json")


def destroy(binding, metadata=None):
    owned(binding)
    if metadata:
        if (metadata.get("container_id") != binding["container_id"] or metadata.get("image_id") != binding["image_id"]
                or not re.fullmatch(r"aryn-operational-[a-f0-9]{32}", metadata.get("image_tag", ""))
                or docker("image", "inspect", metadata["image_tag"], "--format", "{{.Id}}") != binding["image_id"]):
            raise RuntimeError("Owned image cleanup identity differs.")
    docker("rm", "--force", binding["container_id"])
    if metadata:
        # Remove only this environment's tag. Shared base images/layers and
        # other references to the same content-addressed image are preserved.
        docker("image", "rm", metadata["image_tag"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["create", "observe", "fault", "destroy"])
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--base-image")
    parser.add_argument("--organization", default="operational_org")
    parser.add_argument("--project", default="operational_project")
    parser.add_argument("--fault", choices=["stop_worker", "latch_unhealthy"], default="stop_worker")
    parser.add_argument("--ttl", type=int, default=3600)
    args = parser.parse_args()
    if args.action == "create":
        if args.manifest.exists() or build_record(args.manifest).exists() or not args.manifest.parent.is_dir():
            raise ValueError("Manifest must be a new file in an existing owned directory.")
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", args.base_image or ""):
            raise ValueError("An already reviewed immutable local base image ID is required.")
        if not all(re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value)
                for value in [args.organization, args.project]) or not 30 <= args.ttl <= 28800:
            raise ValueError("Scope or lifetime differs.")
        image_tag = "aryn-operational-" + uuid.uuid4().hex
        if docker("image", "inspect", args.base_image, "--format", "{{.Id}}") != args.base_image:
            raise ValueError("Reviewed base image is not present locally.")
        context = Path(__file__).resolve().parents[1] / "docker" / "operational_targets"
        source_hashes = {name: hashlib.sha256((context / name).read_bytes()).hexdigest()
            for name in ("Dockerfile", ".dockerignore", "service.py")}
        docker("build", "--network", "none", "--pull=false", "--build-arg", f"BASE_IMAGE={args.base_image}",
            "--tag", image_tag, str(context), timeout=120)
        image_id = docker("image", "inspect", image_tag, "--format", "{{.Id}}")
        environment_id = uuid.uuid4().hex
        try:
            container = docker("run", "--detach", "--pull", "never", "--name", "aryn-operational-" + environment_id,
                "--label", "aryn.operational.environment=" + environment_id,
                "--label", "aryn.organization=" + args.organization, "--label", "aryn.project=" + args.project,
                "--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                "--user", PROFILE["user"], "--memory", "128m", "--memory-swap", "128m", "--cpus", "0.5",
                "--pids-limit", "64", "--init", image_id, "serve", "--ttl", str(args.ttl))
        except BaseException:
            docker("image", "rm", image_tag)
            raise
        binding = {"binding_id": "service_" + environment_id, "environment_id": environment_id,
            "organization_id": args.organization, "project_id": args.project,
            "container_id": container, "image_id": image_id, "profile": PROFILE}
        try:
            owned(binding)
            if source_hashes != {name: hashlib.sha256((context / name).read_bytes()).hexdigest() for name in source_hashes}:
                raise RuntimeError("Build sources changed during creation.")
            with build_record(args.manifest).open("x", encoding="utf-8") as stream:
                json.dump({"image_tag": image_tag, "image_id": image_id, "base_image_id": args.base_image,
                    "container_id": container, "source_sha256": source_hashes}, stream, indent=2)
            with args.manifest.open("x", encoding="utf-8") as stream:
                json.dump({"schema_version": 1, "targets": [binding]}, stream, indent=2)
        except BaseException:
            docker("rm", "--force", container)
            docker("image", "rm", image_tag)
            raise
        print(json.dumps({"manifest": str(args.manifest.resolve()), "binding_id": binding["binding_id"]}))
        return
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    for binding in manifest["targets"]:
        owned(binding)
        if args.action == "destroy":
            metadata_path = build_record(args.manifest)
            metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else None
            destroy(binding, metadata)
            print(json.dumps({"destroyed": binding["environment_id"], "owned_image_tag_removed": metadata is not None}))
        else:
            mode = "control" if args.action == "fault" else "observe"
            payload = json.dumps({"action": args.fault}).encode() if args.action == "fault" else None
            print(docker("exec", "--interactive", binding["container_id"], "python", "-B",
                "/opt/aryn/operational_service.py", mode, data=payload, timeout=10))


if __name__ == "__main__":
    main()
