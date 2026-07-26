"""Export or migrate TERM Bridge add-on options."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from term_bridge.config import ConfigError, build_options, load_raw_options

TLS_DEFAULTS: dict[str, Any] = {
    "mqtt_tls": False,
    "mqtt_tls_ca": "",
    "mqtt_tls_cert": "",
    "mqtt_tls_key": "",
}


def prepare_options(source: str, *, redact_secrets: bool = False) -> dict[str, Any]:
    raw = {**TLS_DEFAULTS, **load_raw_options(source)}
    build_options(raw)
    if redact_secrets and raw.get("mqtt_password"):
        raw["mqtt_password"] = "<redacted>"
    return raw


def write_export(options: dict[str, Any], output: str) -> None:
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(options, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if os.name != "nt":
        target.chmod(0o600)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="/data/options.json", help="source options.json")
    parser.add_argument("--output", required=True, help="destination JSON file")
    parser.add_argument(
        "--redact-secrets",
        action="store_true",
        help="replace the MQTT password; redacted output cannot be imported directly",
    )
    args = parser.parse_args()

    try:
        options = prepare_options(args.source, redact_secrets=args.redact_secrets)
        write_export(options, args.output)
    except ConfigError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
