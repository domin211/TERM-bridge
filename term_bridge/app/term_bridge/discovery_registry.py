"""Persistent record of zone IDs whose retained MQTT topics TERM Bridge owns."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

log = logging.getLogger("term_bridge.discovery_registry")


class DiscoveryRegistry:
    def __init__(self, path: str | None) -> None:
        self.path = Path(path) if path else None
        self._controllers: dict[str, set[str]] = {}
        self._load()

    def _load(self) -> None:
        if self.path is None:
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            controllers = raw.get("controllers", {}) if isinstance(raw, dict) else {}
            if not isinstance(controllers, dict):
                raise ValueError("controllers must be an object")
            self._controllers = {
                str(key): {str(item) for item in values}
                for key, values in controllers.items()
                if isinstance(values, list)
            }
        except FileNotFoundError:
            return
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            log.warning("Ignoring invalid discovery registry %s: %s", self.path, exc)

    def previous(self, controller_key: str) -> set[str]:
        return set(self._controllers.get(controller_key, set()))

    def replace(self, controller_key: str, unique_ids: set[str]) -> None:
        self._controllers[controller_key] = set(unique_ids)
        self._save()

    def _save(self) -> None:
        if self.path is None:
            return
        payload = {
            "version": 1,
            "controllers": {
                key: sorted(values)
                for key, values in sorted(self._controllers.items())
            },
        }
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            os.replace(temporary, self.path)
        except OSError as exc:
            log.error("Could not persist discovery registry %s: %s", self.path, exc)
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
