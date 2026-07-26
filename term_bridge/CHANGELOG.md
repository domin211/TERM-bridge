# Changelog

## 5.1.4

- Fixed duplicated Home Assistant names by making each climate entity the main
  feature of its zone device.
- Added preferred default entity IDs such as `climate.21_pokoj`.
- Added a one-time cleanup of retained discovery/state/command topics from both
  TERM Bridge and the previous HMPD namespace.
- Added a persistent discovery registry that removes retained MQTT topics for
  zones that disappear or are renamed after a restart.

## 5.1.3

- Removed the overly restrictive custom AppArmor policy that blocked container
  DNS resolution and Python package discovery.
- Restored Home Assistant's default AppArmor protection profile.
- Added a complete container smoke test using hostname-based MQTT discovery and
  a simulated serial controller.

## 5.1.2

- Fixed AppArmor read/traversal access for the immutable Python application and
  virtual-environment package trees.

## 5.1.1

- Fixed AppArmor execution rules for virtual-environment Python and BusyBox
  utilities used by the restart runner.

## 5.1.0

- Added a Home Assistant connectivity sensor for every configured controller.
- Added retained controller online/offline state and failure details.
- Added MQTT TLS with mandatory certificate and hostname validation.
- Added stable, installation-specific MQTT client identities.
- Added strict configuration validation and an options transfer helper.
- Added structured bridge and controller health diagnostics.
- Added an AppArmor profile and hardened the container runtime.
- Added hashed runtime dependencies and a digest-pinned Alpine base image.
- Added dependency auditing, CodeQL, dependency review, and container vulnerability scanning.
- Added disposable Mosquitto integration tests.
- Reduced sensitive controller output to debug logging.
