import json

from term_bridge.discovery_registry import DiscoveryRegistry


def test_registry_persists_zone_ids_by_controller(tmp_path):
    path = tmp_path / "registry.json"
    registry = DiscoveryRegistry(str(path))
    registry.replace("usb0", {"usb0_2", "usb0_1"})

    reloaded = DiscoveryRegistry(str(path))

    assert reloaded.previous("usb0") == {"usb0_1", "usb0_2"}
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 1


def test_registry_replaces_only_selected_controller(tmp_path):
    path = tmp_path / "registry.json"
    registry = DiscoveryRegistry(str(path))
    registry.replace("usb0", {"a"})
    registry.replace("usb1", {"b"})
    registry.replace("usb0", {"c"})

    reloaded = DiscoveryRegistry(str(path))

    assert reloaded.previous("usb0") == {"c"}
    assert reloaded.previous("usb1") == {"b"}


def test_invalid_registry_is_ignored(tmp_path):
    path = tmp_path / "registry.json"
    path.write_text("{broken", encoding="utf-8")

    registry = DiscoveryRegistry(str(path))

    assert registry.previous("usb0") == set()
