import json
import os
import socket
import subprocess
import threading
import time
import uuid

import paho.mqtt.client as mqtt
import pytest

from term_bridge.config import get_or_create_client_id


def _wait_for_port(port: int, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f"Mosquitto did not open port {port}")


@pytest.fixture
def mosquitto(tmp_path):
    if os.getenv("RUN_MQTT_INTEGRATION") != "1":
        pytest.skip("set RUN_MQTT_INTEGRATION=1 to run the Docker-backed MQTT test")

    config = tmp_path / "mosquitto.conf"
    config.write_text("listener 1883 0.0.0.0\nallow_anonymous true\npersistence false\n", encoding="utf-8")
    container = subprocess.check_output(
        [
            "docker",
            "run",
            "--rm",
            "--detach",
            "--publish",
            "127.0.0.1::1883",
            "--volume",
            f"{config.resolve()}:/mosquitto/config/mosquitto.conf:ro",
            "eclipse-mosquitto:2",
        ],
        text=True,
    ).strip()
    try:
        published = subprocess.check_output(["docker", "port", container, "1883/tcp"], text=True).strip()
        port = int(published.rsplit(":", 1)[1])
        _wait_for_port(port)
        yield port
    finally:
        subprocess.run(["docker", "stop", "--time", "1", container], check=False, capture_output=True)


@pytest.mark.integration
def test_two_installations_connect_and_exchange_health(mosquitto, tmp_path):
    received = threading.Event()
    payloads: list[dict[str, object]] = []
    topic = f"term-bridge-test/{uuid.uuid4().hex}/health"

    subscriber = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=get_or_create_client_id(str(tmp_path / "subscriber-id")),
    )
    publisher = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=get_or_create_client_id(str(tmp_path / "publisher-id")),
    )

    def on_message(client, userdata, message):
        payloads.append(json.loads(message.payload))
        received.set()

    subscriber.on_message = on_message
    subscriber.connect("127.0.0.1", mosquitto)
    publisher.connect("127.0.0.1", mosquitto)
    subscriber.subscribe(topic)
    subscriber.loop_start()
    publisher.loop_start()
    try:
        publisher.publish(topic, json.dumps({"status": "online"}), qos=1).wait_for_publish(timeout=5)
        assert received.wait(timeout=5)
        assert payloads == [{"status": "online"}]
    finally:
        publisher.disconnect()
        subscriber.disconnect()
        publisher.loop_stop()
        subscriber.loop_stop()
