"""MQTT topic naming and Home Assistant MQTT-discovery payloads."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from .config import Controller, TempRange
from .models import Zone


def zone_unique_id(controller_key: str, zone_index: int) -> str:
    return f"{controller_key}_{int(zone_index)}"


def entity_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", normalized.lower()).strip("_") or "unnamed"


@dataclass(frozen=True)
class Topics:
    discovery_prefix: str
    base_topic: str

    def state(self, unique_id: str) -> str:
        return f"{self.base_topic}/{unique_id}/state"

    def command(self, unique_id: str) -> str:
        return f"{self.base_topic}/{unique_id}/set_target"

    def discovery(self, unique_id: str) -> str:
        return f"{self.discovery_prefix}/climate/term_bridge_{unique_id}/config"

    def bridge_status(self) -> str:
        return f"{self.base_topic}/bridge/status"

    def bridge_resync(self) -> str:
        return f"{self.base_topic}/bridge/resync"

    def bridge_health(self) -> str:
        return f"{self.base_topic}/bridge/health"

    def controller_status(self, controller_key: str) -> str:
        return f"{self.base_topic}/controller/{controller_key}/status"

    def controller_status_discovery(self, controller_key: str) -> str:
        return f"{self.discovery_prefix}/binary_sensor/term_bridge_controller_{controller_key}/config"

    def set_target_subscription(self) -> str:
        return f"{self.base_topic}/+/set_target"

    def discovery_payload(self, zone: Zone, temp_range: TempRange) -> dict[str, Any]:
        state_topic = self.state(zone.unique_id)
        object_id = f"term_bridge_{zone.unique_id}"
        return {
            "name": None,
            "object_id": object_id,
            "unique_id": object_id,
            "default_entity_id": f"climate.{entity_slug(zone.zone_name)}",
            "availability_topic": self.bridge_status(),
            "payload_available": "online",
            "payload_not_available": "offline",
            "current_temperature_topic": state_topic,
            "current_temperature_template": "{{ value_json.current_temp }}",
            "temperature_state_topic": state_topic,
            "temperature_state_template": "{{ value_json.target_temp }}",
            "temperature_command_topic": self.command(zone.unique_id),
            "mode_state_topic": state_topic,
            "mode_state_template": "{{ value_json.mode }}",
            "modes": ["off", "heat"],
            "min_temp": temp_range.minimum,
            "max_temp": temp_range.maximum,
            "temp_step": temp_range.step,
            "device": {
                "identifiers": [f"term_bridge_{zone.unique_id}"],
                "name": zone.zone_name,
                "manufacturer": "HMPD",
                "model": "Thermostat Regulator",
                "via_device": f"term_bridge_{zone.controller_key}",
            },
            "suggested_area": zone.controller_name,
            "origin": {
                "name": "TERM Bridge",
                "support_url": "https://github.com/domin211/TERM-bridge",
            },
        }

    def state_payload(self, zone: Zone, temp_range: TempRange, mode: str) -> dict[str, Any]:
        current_temp = zone.current_temp if zone.current_temp is not None else temp_range.minimum
        target_temp = zone.target_temp if zone.target_temp is not None else temp_range.minimum
        return {
            "current_temp": current_temp,
            "target_temp": target_temp,
            "mode": mode,
        }

    def controller_status_payload(self, controller: Controller) -> dict[str, Any]:
        object_id = f"term_bridge_controller_{controller.key}"
        return {
            "name": None,
            "object_id": object_id,
            "unique_id": object_id,
            "default_entity_id": f"binary_sensor.{entity_slug(controller.name)}_controller",
            "device_class": "connectivity",
            "state_topic": self.controller_status(controller.key),
            "payload_on": "online",
            "payload_off": "offline",
            "availability_topic": self.bridge_status(),
            "payload_available": "online",
            "payload_not_available": "offline",
            "entity_category": "diagnostic",
            "device": {
                "identifiers": [f"term_bridge_{controller.key}"],
                "name": f"{controller.name} Controller",
                "manufacturer": "TERM Bridge",
                "model": "HMPD Serial Controller",
            },
            "origin": {
                "name": "TERM Bridge",
                "support_url": "https://github.com/domin211/TERM-bridge",
            },
        }


def controller_log_label(controller: Controller) -> str:
    return f"{controller.name} ({controller.dev} @ {controller.baud}, key={controller.key})"
