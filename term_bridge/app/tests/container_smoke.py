"""Run the finished image against Mosquitto and a simulated HMPD controller."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

IMAGE = "term-bridge-add-on"


def docker(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], check=check, capture_output=True, text=True)


def wait_for_log(container: str, messages: tuple[str, ...], timeout: float = 30.0) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = docker("logs", container, check=False)
        logs = result.stdout + result.stderr
        if all(message in logs for message in messages):
            return logs
        if docker("inspect", "-f", "{{.State.Running}}", container, check=False).stdout.strip() == "false":
            raise RuntimeError(f"{container} stopped unexpectedly:\n{logs}")
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for {messages!r} in {container} logs:\n{logs}")


def main() -> None:
    suffix = uuid.uuid4().hex[:10]
    network = f"term-bridge-smoke-{suffix}"
    broker = f"term-bridge-broker-{suffix}"
    app = f"term-bridge-app-{suffix}"

    with tempfile.TemporaryDirectory(prefix="term-bridge-smoke-") as temp:
        root = Path(temp)
        data_dir = root / "data"
        config_dir = root / "config"
        data_dir.mkdir()
        config_dir.mkdir()

        broker_config = root / "mosquitto.conf"
        broker_config.write_text(
            "listener 1883 0.0.0.0\nallow_anonymous true\npersistence false\n",
            encoding="utf-8",
        )

        fake_hmpd = config_dir / "fake_hmpd"
        fake_hmpd.write_bytes(
            b"#!/bin/sh\n"
            b'case " $* " in\n'
            b'  *" temps"*) echo "0: 21.5" ;;\n'
            b'  *" regs"*) echo "0 | Test zone | cur: 21.5 | tgt: 22.0 | EN" ;;\n'
            b'  *" set "*) exit 0 ;;\n'
            b"esac\n"
        )
        if os.name != "nt":
            fake_hmpd.chmod(0o755)

        options = {
            "debug": False,
            "mqtt_host": broker,
            "mqtt_port": 1883,
            "mqtt_username": "",
            "mqtt_password": "",
            "mqtt_tls": False,
            "mqtt_tls_ca": "",
            "mqtt_tls_cert": "",
            "mqtt_tls_key": "",
            "hmpd_path": "/config/fake_hmpd",
            "controllers": [
                {
                    "name": "smoke",
                    "dev": "/dev/null",
                    "baud": 4800,
                    "expected_regs": 1,
                }
            ],
        }
        (data_dir / "options.json").write_text(json.dumps(options), encoding="utf-8")

        try:
            docker("network", "create", network)
            docker(
                "run",
                "--detach",
                "--name",
                broker,
                "--network",
                network,
                "--volume",
                f"{broker_config.resolve()}:/mosquitto/config/mosquitto.conf:ro",
                "eclipse-mosquitto:2",
            )
            docker(
                "run",
                "--detach",
                "--name",
                app,
                "--network",
                network,
                "--volume",
                f"{data_dir.resolve()}:/data",
                "--volume",
                f"{config_dir.resolve()}:/config",
                IMAGE,
            )
            logs = wait_for_log(
                app,
                (
                    f"Connected to MQTT broker {broker}:1883",
                    "One-time MQTT discovery cleanup complete",
                    "Synced regs for smoke",
                    "Cached 1 temperatures for controller smoke",
                ),
            )
            discovery_topic = "homeassistant/climate/term_bridge_smoke_null_0/config"
            discovery = docker(
                "exec",
                broker,
                "mosquitto_sub",
                "-h",
                "localhost",
                "-t",
                discovery_topic,
                "-C",
                "1",
                "-W",
                "5",
            )
            discovery_payload = json.loads(discovery.stdout)
            if discovery_payload["name"] is not None:
                raise RuntimeError(f"Climate entity name must be null: {discovery_payload}")
            if discovery_payload["default_entity_id"] != "climate.test_zone":
                raise RuntimeError(f"Unexpected default entity ID: {discovery_payload}")

            legacy = docker(
                "exec",
                broker,
                "mosquitto_sub",
                "-h",
                "localhost",
                "-t",
                "homeassistant/climate/hmpd_smoke_null_0/config",
                "-C",
                "1",
                "-W",
                "1",
                check=False,
            )
            if legacy.returncode == 0:
                raise RuntimeError(f"Legacy discovery topic still retained: {legacy.stdout}")
            if not (data_dir / "term_bridge_naming_v2_complete").exists():
                raise RuntimeError("Naming migration marker was not persisted")
            registry = json.loads((data_dir / "term_bridge_discovery_registry.json").read_text(encoding="utf-8"))
            if registry["controllers"]["smoke_null"] != ["smoke_null_0"]:
                raise RuntimeError(f"Discovery registry did not persist the active zone: {registry}")
            print(logs)
        finally:
            docker("rm", "--force", app, check=False)
            docker("rm", "--force", broker, check=False)
            docker("network", "rm", network, check=False)


if __name__ == "__main__":
    main()
