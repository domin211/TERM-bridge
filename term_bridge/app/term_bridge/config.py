"""Validated TERM Bridge configuration and installation identity management."""
from __future__ import annotations

import json
import os
import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

OPTIONS_PATH = "/data/options.json"
INSTANCE_ID_PATH = "/data/term_bridge_instance_id"
DISCOVERY_REGISTRY_PATH = "/data/term_bridge_discovery_registry.json"
NAMING_MIGRATION_MARKER_PATH = "/data/term_bridge_naming_v2_complete"

DEFAULT_MQTT_HOST = os.getenv("MQTT_HOST", "core-mosquitto")
DEFAULT_MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
DEFAULT_MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
DEFAULT_MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_DISCOVERY_PREFIX = os.getenv("MQTT_DISCOVERY_PREFIX", "homeassistant")
MQTT_BASE_TOPIC = os.getenv("MQTT_BASE_TOPIC", "term_bridge")
MQTT_KEEPALIVE = 60
MQTT_RETRY_SECONDS = 10

DEFAULT_HMPD_PATH = os.getenv("HMPD_PATH", "/app/hmpd")
HMPD_FIND_RETRY_SECONDS = 30

DEFAULT_CONTROLLERS: list[dict[str, Any]] = [
    {"name": "usb0", "dev": "/dev/ttyUSB0", "baud": 4800, "expected_regs": 64},
    {"name": "usb1", "dev": "/dev/ttyUSB1", "baud": 4800, "expected_regs": 39},
]

CURRENT_TEMP_SYNC_INTERVAL = 60
TARGET_SYNC_INTERVAL = 3600
HEALTH_PUBLISH_INTERVAL = 30
MQTT_DISCOVERY_CLEANUP_DELAY = 5.0
MQTT_LEGACY_ZONE_LIMIT = 64

TEMPS_TIMEOUT = 15
REGS_TIMEOUT = 20
SET_TIMEOUT = 20

COMMAND_GAP_SECONDS = 3.0
MAX_COMMAND_ATTEMPTS = 5
RETRY_DELAYS_SECONDS = [5, 10, 60, 60]

TEMP_MIN = 16.0
TEMP_MAX = 32.0
TEMP_STEP = 1.0
OFF_MODE_TARGET_THRESHOLD = 18.0

RETAIN_DISCOVERY = True
RETAIN_STATE = True

DEBUG_LOG_FILE = "/config/term_bridge.log"
DEBUG_LOG_MAX_BYTES = 10 * 1024 * 1024
DEBUG_LOG_BACKUP_COUNT = 5


class ConfigError(ValueError):
    """Raised when add-on options are malformed or unsafe."""


@dataclass(frozen=True)
class TempRange:
    minimum: float = TEMP_MIN
    maximum: float = TEMP_MAX
    step: float = TEMP_STEP

    def snap(self, value: float) -> float:
        clamped = max(self.minimum, min(self.maximum, value))
        steps = round((clamped - self.minimum) / self.step)
        snapped = self.minimum + steps * self.step
        return round(max(self.minimum, min(self.maximum, snapped)), 1)


@dataclass(frozen=True)
class Controller:
    name: str
    dev: str
    baud: int
    expected_regs: int = 64

    @property
    def key(self) -> str:
        base = os.path.basename(self.dev) or self.name
        value = f"{self.name}_{base}"
        value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
        value = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
        return value or self.name.lower()


@dataclass(frozen=True)
class Options:
    debug: bool = False
    mqtt_host: str = DEFAULT_MQTT_HOST
    mqtt_port: int = DEFAULT_MQTT_PORT
    mqtt_username: str = DEFAULT_MQTT_USERNAME
    mqtt_password: str = DEFAULT_MQTT_PASSWORD
    mqtt_tls: bool = False
    mqtt_tls_ca: str = ""
    mqtt_tls_cert: str = ""
    mqtt_tls_key: str = ""
    mqtt_client_id: str | None = None
    instance_id_path: str = INSTANCE_ID_PATH
    discovery_registry_path: str | None = DISCOVERY_REGISTRY_PATH
    naming_migration_marker_path: str | None = NAMING_MIGRATION_MARKER_PATH
    hmpd_path: str = DEFAULT_HMPD_PATH
    controllers: tuple[Controller, ...] = field(default_factory=tuple)
    discovery_prefix: str = MQTT_DISCOVERY_PREFIX
    base_topic: str = MQTT_BASE_TOPIC
    temp_range: TempRange = field(default_factory=TempRange)


def _expect_bool(raw: dict[str, Any], name: str, default: bool) -> bool:
    value = raw.get(name, default)
    if not isinstance(value, bool):
        raise ConfigError(f"{name} must be a boolean")
    return value


def _expect_string(
    raw: dict[str, Any],
    name: str,
    default: str,
    *,
    required: bool = False,
    strip: bool = True,
) -> str:
    value = raw.get(name, default)
    if not isinstance(value, str):
        raise ConfigError(f"{name} must be a string")
    if strip:
        value = value.strip()
    if required and not value:
        raise ConfigError(f"{name} must not be empty")
    return value


def _expect_port(raw: dict[str, Any]) -> int:
    value = raw.get("mqtt_port", DEFAULT_MQTT_PORT)
    if isinstance(value, bool):
        raise ConfigError("mqtt_port must be an integer between 1 and 65535")
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError("mqtt_port must be an integer between 1 and 65535") from exc
    if not 1 <= port <= 65535:
        raise ConfigError("mqtt_port must be between 1 and 65535")
    return port


def _build_controllers(raw: Any) -> tuple[Controller, ...]:
    items = DEFAULT_CONTROLLERS if raw is None else raw
    if not isinstance(items, list) or not items:
        raise ConfigError("controllers must be a non-empty list")

    controllers: list[Controller] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ConfigError(f"controllers[{index}] must be an object")
        try:
            name = str(item["name"]).strip()
            dev = str(item["dev"]).strip()
            baud = int(item["baud"])
            expected_regs = int(item.get("expected_regs", 64))
        except (KeyError, TypeError, ValueError) as exc:
            raise ConfigError(
                f"controllers[{index}] requires name, dev, positive baud, and positive expected_regs"
            ) from exc
        if not name or not dev or baud <= 0 or expected_regs <= 0:
            raise ConfigError(
                f"controllers[{index}] requires name, dev, positive baud, and positive expected_regs"
            )
        controllers.append(Controller(name=name, dev=dev, baud=baud, expected_regs=expected_regs))

    keys = [controller.key for controller in controllers]
    if len(keys) != len(set(keys)):
        raise ConfigError("controllers must resolve to unique name/device keys")
    return tuple(controllers)


def load_raw_options(path: str = OPTIONS_PATH) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as options_file:
            data = json.load(options_file)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {path}: {exc.msg} at line {exc.lineno}, column {exc.colno}") from exc
    except OSError as exc:
        raise ConfigError(f"Could not read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a JSON object")
    return data


def build_options(raw: dict[str, Any]) -> Options:
    if not isinstance(raw, dict):
        raise ConfigError("options must be a JSON object")

    mqtt_tls = _expect_bool(raw, "mqtt_tls", False)
    tls_ca = _expect_string(raw, "mqtt_tls_ca", "")
    tls_cert = _expect_string(raw, "mqtt_tls_cert", "")
    tls_key = _expect_string(raw, "mqtt_tls_key", "")
    if bool(tls_cert) != bool(tls_key):
        raise ConfigError("mqtt_tls_cert and mqtt_tls_key must be configured together")
    if (tls_ca or tls_cert or tls_key) and not mqtt_tls:
        raise ConfigError("mqtt_tls must be enabled when TLS certificate options are configured")

    return Options(
        debug=_expect_bool(raw, "debug", False),
        mqtt_host=_expect_string(raw, "mqtt_host", DEFAULT_MQTT_HOST, required=True),
        mqtt_port=_expect_port(raw),
        mqtt_username=_expect_string(raw, "mqtt_username", DEFAULT_MQTT_USERNAME),
        mqtt_password=_expect_string(raw, "mqtt_password", DEFAULT_MQTT_PASSWORD, strip=False),
        mqtt_tls=mqtt_tls,
        mqtt_tls_ca=tls_ca,
        mqtt_tls_cert=tls_cert,
        mqtt_tls_key=tls_key,
        hmpd_path=_expect_string(raw, "hmpd_path", DEFAULT_HMPD_PATH, required=True),
        controllers=_build_controllers(raw.get("controllers")),
    )


def get_or_create_client_id(path: str = INSTANCE_ID_PATH) -> str:
    identity_path = Path(path)
    try:
        existing = identity_path.read_text(encoding="ascii").strip()
    except FileNotFoundError:
        existing = ""
    except OSError as exc:
        raise ConfigError(f"Could not read installation identity {path}: {exc}") from exc

    if re.fullmatch(r"[0-9a-f]{12}", existing):
        suffix = existing
    else:
        suffix = uuid.uuid4().hex[:12]
        try:
            identity_path.parent.mkdir(parents=True, exist_ok=True)
            identity_path.write_text(f"{suffix}\n", encoding="ascii")
        except OSError as exc:
            raise ConfigError(f"Could not persist installation identity {path}: {exc}") from exc
    return f"term_bridge_{suffix}"


def load_options(path: str = OPTIONS_PATH) -> Options:
    return build_options(load_raw_options(path))
