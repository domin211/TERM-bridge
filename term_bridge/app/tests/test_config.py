import json

import pytest

from term_bridge.config import (
    ConfigError,
    Controller,
    TempRange,
    build_options,
    get_or_create_client_id,
    load_raw_options,
)


def test_controller_key_normalizes_name_and_device():
    controller = Controller(name="usb0", dev="/dev/ttyUSB0", baud=4800)
    assert controller.key == "usb0_ttyusb0"


def test_controller_key_strips_accents_and_symbols():
    controller = Controller(name="Kotelna #1", dev="/dev/ttyÚSB0", baud=4800)
    assert controller.key == controller.key.lower()
    assert all(c.isalnum() or c == "_" for c in controller.key)


def test_temp_range_snaps_to_nearest_step():
    temp_range = TempRange(minimum=16.0, maximum=32.0, step=1.0)
    assert temp_range.snap(21.4) == 21.0
    assert temp_range.snap(21.6) == 22.0


def test_temp_range_clamps_out_of_bounds():
    temp_range = TempRange(minimum=16.0, maximum=32.0, step=1.0)
    assert temp_range.snap(5.0) == 16.0
    assert temp_range.snap(100.0) == 32.0


def test_build_options_defaults_when_empty():
    options = build_options({})
    assert options.debug is False
    assert options.mqtt_host == "core-mosquitto"
    assert len(options.controllers) == 2
    assert {c.name for c in options.controllers} == {"usb0", "usb1"}


def test_build_options_uses_configured_controllers():
    raw = {
        "debug": True,
        "mqtt_host": "broker.local",
        "controllers": [{"name": "usb2", "dev": "/dev/ttyUSB2", "baud": 9600, "expected_regs": 10}],
    }
    options = build_options(raw)
    assert options.debug is True
    assert options.mqtt_host == "broker.local"
    assert len(options.controllers) == 1
    assert options.controllers[0].expected_regs == 10


def test_tls_configuration_is_exposed():
    options = build_options(
        {
            "mqtt_tls": True,
            "mqtt_tls_ca": "/config/ca.pem",
            "mqtt_tls_cert": "/config/client.pem",
            "mqtt_tls_key": "/config/client.key",
        }
    )
    assert options.mqtt_tls is True
    assert options.mqtt_tls_ca == "/config/ca.pem"


def test_mqtt_password_preserves_whitespace():
    assert build_options({"mqtt_password": " leading and trailing "}).mqtt_password == " leading and trailing "


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ({"mqtt_port": 0}, "mqtt_port"),
        ({"debug": "yes"}, "debug"),
        ({"controllers": []}, "controllers"),
        ({"mqtt_tls_cert": "/cert.pem"}, "mqtt_tls"),
        ({"mqtt_tls": True, "mqtt_tls_cert": "/cert.pem"}, "configured together"),
    ],
)
def test_invalid_configuration_is_rejected(raw, message):
    with pytest.raises(ConfigError, match=message):
        build_options(raw)


def test_malformed_options_file_is_rejected(tmp_path):
    path = tmp_path / "options.json"
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ConfigError, match="Invalid JSON"):
        load_raw_options(str(path))


def test_non_object_options_file_is_rejected(tmp_path):
    path = tmp_path / "options.json"
    path.write_text(json.dumps(["wrong"]), encoding="utf-8")
    with pytest.raises(ConfigError, match="JSON object"):
        load_raw_options(str(path))


def test_client_id_is_unique_and_persistent(tmp_path):
    first_path = tmp_path / "one" / "id"
    second_path = tmp_path / "two" / "id"

    first = get_or_create_client_id(str(first_path))
    assert get_or_create_client_id(str(first_path)) == first
    assert get_or_create_client_id(str(second_path)) != first
    assert first.startswith("term_bridge_")
