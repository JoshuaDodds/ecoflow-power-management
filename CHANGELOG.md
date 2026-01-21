# Changelog

All notable changes to the EcoFlow Power Management project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

**Versioning:** This project uses [Calendar Versioning](https://calver.org/) with format `YYYY.MM.DD.HH` (Europe/Amsterdam timezone) to match container image tags.

## [2026.01.21.10] - 2026-01-21

### Changed
- **Versioning scheme**: Switched from SemVer to CalVer (`YYYY.MM.DD.HH`)
  - Matches GitHub workflow container image versioning
  - Eliminates confusion between release tags and image tags
  - All releases now use consistent CalVer format
- **BREAKING**: Removed Cloud API credentials requirement (username/password)
  - Only Developer API credentials (Access Key/Secret Key) now required
  - Simplified setup process significantly
  - Updated all documentation to reflect new requirements
- Updated config validator to only check Developer API credentials
- Removed `host_agent` from service list (not implemented)

### Added
- **Comprehensive SETUP.md**: Step-by-step installation guide
  - MQTT broker installation for Linux/macOS/Windows/Docker
  - Developer API credential acquisition guide
  - Configuration examples and troubleshooting
- **tools/README.md**: Explains legacy `ecoflow_get_mqtt_login.sh` script
- **Quick Start section** in README with 30-second overview
- **Documentation section** in README linking to SETUP.md, DOCKER.md, CHANGELOG.md
- Architecture clarification: Mosquitto bridge config NOT needed
- AI collaboration disclosure (Gemini 3.0 Pro & Claude Sonnet 4.5)

### Fixed
- Dockerfile now includes `__version__.py` (fixes "vunknown" display)
- Config summary no longer displays username (not used)

### Documentation
- Clarified that `ecoflow_cloud_bridge.py` replaces Mosquitto bridges
- Added mermaid architecture diagram back to README
- Updated all credential examples to remove username/password
- Improved troubleshooting sections

### Verified
- System works without Cloud API credentials (username/password)
- Mosquitto bridge configuration confirmed unnecessary
- All services connect and operate correctly with only Developer API

---

## [0.1.0-alpha] - 2026-01-20


### Added
- **Initial alpha release** of EcoFlow Power Management Orchestrator
- **EcoFlow Cloud Bridge**: Connects to EcoFlow MQTT cloud and streams device telemetry
- **SOC Bridge**: Decodes Protobuf messages into normalized JSON format
- **Policy Engine**: Decision-making service with debounce, cooldown, and abort logic
- **Multi-platform agents**: Ready-to-use shutdown listeners for Linux, Windows, and macOS
- **Strict grid detection**: Accurate grid status detection for River 3 Plus devices
- **Configuration validation**: Helpful error messages for missing or invalid configuration
- **Version tracking**: Displays version on startup (`v0.1.0-alpha`)
- **Comprehensive test suite**: Unit tests for env_loader, policy_engine, and config validation
- **Multi-line JSON support**: Environment loader handles multi-line `DEVICE_TO_AGENTS_JSON`
- **Simulation tools**: Test policy logic without draining physical batteries
- **Documentation**: Comprehensive README, agent setup guides, and Docker deployment guide

### Fixed
- **AttributeError in policy_engine**: Fixed crash when `DEVICE_TO_AGENTS_JSON` parsing fails
  - All critical attributes now initialized before try block
  - Graceful degradation with default values
- **Multi-line JSON parsing**: Enhanced `env_loader.py` to support multi-line environment values

### Known Issues
- Limited testing on non-River 3 Plus EcoFlow devices
- Health check endpoint not yet implemented
- Agent scripts tested primarily on: Ubuntu 22.04, Windows 11, macOS 14+
- MQTT broker must be network-accessible to all agents

### Security
- Proper `.gitignore` configuration excludes sensitive `.env` files
- Example configurations properly sanitized
- No hardcoded credentials in source code

---

## Release Notes

This is an **alpha release** intended for early testing and feedback. While the core functionality is working and has been tested in production environments, users should:

- **Test thoroughly** before relying on it for critical systems
- **Monitor logs** during initial deployment
- **Report issues** on GitHub
- **Share feedback** on compatibility with different EcoFlow models

**Development Note:** This project was developed in collaboration with AI assistants (Google Gemini 3.0 Pro and Anthropic Claude Sonnet 4.5) to accelerate development and improve code quality. All code has been reviewed, tested, and validated.

### Tested Configurations
- **Devices**: River 3 Plus (primary testing)
- **Operating Systems**: 
  - Ubuntu 22.04 (server)
  - Windows 11 (agent)
  - macOS 14+ (agent)
- **MQTT Broker**: Mosquitto 2.x

### Community Feedback Needed
- Testing on other EcoFlow models (Delta, River 2, etc.)
- Agent compatibility on other OS versions
- Network topology variations (VLANs, Docker networks, etc.)
- Edge cases and failure scenarios

---

[2026.01.21.10]: https://github.com/JoshuaDodds/ecoflow-power-management/releases/tag/2026.01.21.10
[0.1.0-alpha]: https://github.com/JoshuaDodds/ecoflow-power-management/releases/tag/v0.1.0-alpha

