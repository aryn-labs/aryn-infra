"""Lifecycle identity and cleanup boundaries; actual service proof runs in ARYN."""

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("operational_environment", Path(__file__).resolve().parents[1] / "scripts" / "operational_environment.py")
lifecycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lifecycle)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.binding = {"container_id": "a" * 64, "image_id": "sha256:" + "b" * 64,
            "environment_id": "c" * 32, "organization_id": "org", "project_id": "project"}
        self.inspect = {"Id": self.binding["container_id"], "Image": self.binding["image_id"],
            "Mounts": [], "NetworkSettings": {"Networks": {"none": {}}},
            "Config": {"User": "65532:65532", "Labels": {"aryn.operational.environment": "c" * 32,
                "aryn.organization": "org", "aryn.project": "project"}},
            "HostConfig": {"NetworkMode": "none", "ReadonlyRootfs": True, "Privileged": False,
                "Binds": None, "PublishAllPorts": False, "UsernsMode": "", "PortBindings": {},
                "Memory": 134217728, "MemorySwap": 134217728, "Devices": [], "PidMode": "", "IpcMode": "private",
                "NanoCpus": 500000000, "PidsLimit": 64, "CapDrop": ["ALL"], "CapAdd": [], "SecurityOpt": ["no-new-privileges"]}}

    def test_owned_profile_and_missing_optional_tmpfs(self):
        with patch.object(lifecycle, "docker", return_value=json.dumps([self.inspect])):
            lifecycle.owned(self.binding)

    def test_isolation_drift_refuses_lifecycle(self):
        for key, value in {"NetworkMode": "host", "ReadonlyRootfs": False, "Memory": 0,
                "MemorySwap": -1, "PidsLimit": 0, "Tmpfs": {"/host": "rw"}, "Devices": ["/dev/sda"]}.items():
            with self.subTest(key=key):
                modified = copy.deepcopy(self.inspect)
                modified["HostConfig"][key] = value
                with patch.object(lifecycle, "docker", return_value=json.dumps([modified])), self.assertRaises(RuntimeError):
                    lifecycle.owned(self.binding)

    def test_destroy_removes_only_exact_owned_tag_and_container(self):
        tag = "aryn-operational-" + "d" * 32
        calls = []

        def docker(*arguments, **kwargs):
            calls.append(arguments)
            if arguments[0] == "inspect":
                return json.dumps([self.inspect])
            if arguments[:2] == ("image", "inspect"):
                return self.binding["image_id"]
            return ""

        with patch.object(lifecycle, "docker", side_effect=docker):
            lifecycle.destroy(self.binding, {"container_id": self.binding["container_id"],
                "image_id": self.binding["image_id"], "image_tag": tag})
        self.assertEqual(calls[-2:], [("rm", "--force", self.binding["container_id"]), ("image", "rm", tag)])

    def test_forged_cleanup_metadata_does_not_remove_resources(self):
        with patch.object(lifecycle, "docker", return_value=json.dumps([self.inspect])) as docker, self.assertRaises(RuntimeError):
            lifecycle.destroy(self.binding, {"container_id": "f" * 64})
        self.assertEqual(docker.call_count, 1)

    def test_creation_records_source_and_immutable_image_identity(self):
        base, tag, calls = "sha256:" + "e" * 64, None, []

        def docker(*arguments, **kwargs):
            nonlocal tag
            calls.append(arguments)
            if arguments[0] == "build":
                tag = arguments[arguments.index("--tag") + 1]
            if arguments[:2] == ("image", "inspect"):
                return base if arguments[2] == base else self.binding["image_id"]
            if arguments[0] == "run":
                return self.binding["container_id"]
            return ""

        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "environment.json"
            with patch("sys.argv", ["operational_environment", "create", "--manifest", str(manifest), "--base-image", base]), \
                    patch.object(lifecycle, "docker", side_effect=docker), patch.object(lifecycle, "owned"):
                lifecycle.main()
            metadata = json.loads(lifecycle.build_record(manifest).read_text())
            self.assertEqual(metadata["image_tag"], tag)
            self.assertEqual(set(metadata["source_sha256"]), {"Dockerfile", ".dockerignore", "service.py"})
            run = next(arguments for arguments in calls if arguments[0] == "run")
            self.assertIn("--read-only", run)
            self.assertIn("none", run)
            self.assertFalse(any(argument in run for argument in ("--publish", "--volume", "--mount", "--privileged")))


if __name__ == "__main__":
    unittest.main()
