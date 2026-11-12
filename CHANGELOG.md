# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-11-12

### Added
- Per-hashboard diagnostic sensors: hardware errors, rejected shares, and serial
  number.
- Per-miner diagnostic sensor: hardware version.
- Screenshot in the README.

### Changed
- Uptime is now shown in a readable `12d 20h 9m` form instead of raw seconds.

## [0.1.0] - 2026-11-12

### Added
- Initial release.
- QR-code login via the Goldshell Hub, with automatic re-authentication when the
  ~30-day token expires.
- Automatic discovery of every miner on the account (one device per miner).
- Per-hashboard sensors: current and average hashrate, temperature, fan speed,
  and board status.
- Per-miner sensors: status, firmware version, power mode, and uptime.
- English (default) and Brazilian Portuguese (`pt-BR`) translations.

[0.2.0]: https://github.com/rngarcia/ha-goldshell-hub/releases/tag/v0.2.0
[0.1.0]: https://github.com/rngarcia/ha-goldshell-hub/releases/tag/v0.1.0
