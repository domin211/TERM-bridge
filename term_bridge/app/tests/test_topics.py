from term_bridge.config import Controller, TempRange
from term_bridge.models import Zone
from term_bridge.topics import Topics, entity_slug, zone_unique_id


def make_zone(**overrides) -> Zone:
    defaults = dict(
        controller_name="usb0",
        controller_key="usb0_ttyusb0",
        controller_dev="/dev/ttyUSB0",
        zone_index=5,
        zone_name="Room 5",
        unique_id="usb0_ttyusb0_5",
    )
    defaults.update(overrides)
    return Zone(**defaults)


def test_zone_unique_id():
    assert zone_unique_id("usb0_ttyusb0", 5) == "usb0_ttyusb0_5"
    assert entity_slug("Červená Chodba") == "cervena_chodba"


def test_topic_names_match_existing_home_assistant_contract():
    topics = Topics(discovery_prefix="homeassistant", base_topic="term_bridge")
    assert topics.state("z1") == "term_bridge/z1/state"
    assert topics.command("z1") == "term_bridge/z1/set_target"
    assert topics.discovery("z1") == "homeassistant/climate/term_bridge_z1/config"
    assert topics.bridge_status() == "term_bridge/bridge/status"
    assert topics.bridge_resync() == "term_bridge/bridge/resync"
    assert topics.bridge_health() == "term_bridge/bridge/health"
    assert topics.controller_status("usb0") == "term_bridge/controller/usb0/status"
    assert (
        topics.controller_status_discovery("usb0")
        == "homeassistant/binary_sensor/term_bridge_controller_usb0/config"
    )
    assert topics.set_target_subscription() == "term_bridge/+/set_target"


def test_discovery_payload_shape():
    topics = Topics("homeassistant", "term_bridge")
    zone = make_zone()
    payload = topics.discovery_payload(zone, TempRange())

    assert payload["unique_id"] == "term_bridge_usb0_ttyusb0_5"
    assert payload["name"] is None
    assert payload["default_entity_id"] == "climate.room_5"
    assert payload["temperature_command_topic"] == "term_bridge/usb0_ttyusb0_5/set_target"
    assert payload["modes"] == ["off", "heat"]
    assert payload["min_temp"] == 16.0
    assert payload["max_temp"] == 32.0


def test_state_payload_reports_mode_and_falls_back_to_minimum():
    topics = Topics("homeassistant", "term_bridge")
    zone = make_zone(current_temp=None, target_temp=None)
    payload = topics.state_payload(zone, TempRange(), mode="off")

    assert payload == {"current_temp": 16.0, "target_temp": 16.0, "mode": "off"}


def test_controller_connectivity_discovery_payload():
    topics = Topics("homeassistant", "term_bridge")
    controller = Controller(name="Boiler room", dev="/dev/ttyUSB0", baud=4800)

    payload = topics.controller_status_payload(controller)

    assert payload["unique_id"] == f"term_bridge_controller_{controller.key}"
    assert payload["name"] is None
    assert payload["device_class"] == "connectivity"
    assert payload["entity_category"] == "diagnostic"
    assert payload["payload_on"] == "online"
    assert payload["payload_off"] == "offline"
