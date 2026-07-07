# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

BotLab is a Python-based microservices framework for building IoT bot services that run 24/7 in the cloud. Bots analyze real-time and historical data from internet-connected devices to add intelligent features and services. The core runtime (BotEngine) lives in `src/botengine/`; bots themselves are the `com.ppc.*` / `org.ppc.*` directories at the repo root.

## Commands

### Installation
```bash
pip install .                    # Install the package (requires ../botlab-cli checkout)
pip install ".[dev]"             # Install with dev dependencies (pytest, requests_mock)
```

### The `botlab` CLI
```bash
botlab --playback tests/data/14-days-of-data -r com.ppc.Lesson1-Microservices   # Playback recorded data
botlab run <bundle-id> --bot-instance-id <id>    # Run locally against the live server
botlab ls / botlab status                        # List agents / show status
botlab design <bundle-id>                        # Inspect agent architecture
botlab init agent|device|service|signal ...      # Scaffold new components
botlab store upload <bundle-id>                  # Publish to the marketplace
botlab organizations add <bundle-id> --organization-id <org-id>
```

### Running Tests
```bash
pytest                           # Framework tests in tests/ (pytest.ini excludes com.ppc.* and hidden dirs)
pytest tests/test_botengine.py   # Run specific test file
```

For bot microservice testing (tests that require a merged bot runtime environment), use `botlab-tests` (implemented in `src/scripts/pytest.py`):

```bash
botlab-tests                                # Run tests in default bundle (com.ppc.Tests)
botlab-tests --bundle com.ppc.Bot           # Run tests within a specific bot bundle
botlab-tests --directory tests              # Only run the bot's tests/ directory

# Filter down to microservice-related tests (passes through to pytest via `-k`)
botlab-tests --mut meta_analysis
botlab-tests --mut meta_analysis --mut occupancy_analysis

# Run a specific test file (auto-searches microservice tests when used with --mut)
botlab-tests --mut meta_analysis --test-file test_missedbathroom.py
botlab-tests --mut meta_analysis --test-file test_missedbathroom.py::test_function

# Use a different BOTLAB core checkout as the merge source
botlab-tests --core ../botlab-private

# Preload variables / location context for regression-style tests
botlab-tests --variables data.variable --location_id 123

# Verbose pytest output
botlab-tests --verbose
```

Microservice tests run against the stub engine in `src/botengine_pytest/` rather than the live cloud.

### Linting
```bash
ruff check .                     # Check code style (configured in pyproject.toml)
ruff format .                    # Format code
```

## Architecture

### Bot Structure
Bots follow an inheritance model using `structure.json`:
- `com.ppc.Bot` is the foundational bot framework (never edit directly)
- Custom bots extend `com.ppc.Bot` via the `extends` field in `structure.json`
- When generating/committing, files from the parent bot are copied first, then child bot files overlay them; chains of extends are allowed (foundation → business logic → brand)
- `com.ppc.Microservices` holds shared microservice packages that bots pull in via the `microservices` list

### Organization Bots
`org.ppc.*` directories are the organization-scoped counterpart to the location-scoped `com.ppc.*` bots (multi-tenant, org-level operations):
- `org.ppc.Bot`: foundational organization bot framework (does not extend `com.ppc.Bot`)
- `org.ppc.Microservices`: reusable org-level microservices (e.g., organization_settings, billing_per_sub)
- `org.ppc.Tests`: test bundle extending `org.ppc.Bot`

### Core Components

**Entry Point**: `com.ppc.Bot/bot.py`
- `run(botengine)` is the main entry point
- Loads the `Controller`, synchronizes devices, triggers events

**Controller** (`com.ppc.Bot/controller.py`):
- Coordinates all locations and devices
- Manages `Location` objects keyed by location ID

**Location** (`com.ppc.Bot/locations/location.py`):
- Represents a physical location (e.g., home)
- Contains devices, intelligence modules, and filters
- Tracks security state, occupancy status, mode (HOME/AWAY/STAY/TEST)

**Device** (`com.ppc.Bot/devices/device.py`):
- Base class for all device types
- Device-specific implementations in `devices/` subdirectories (alarm, button, camera, entry, motion, etc.)

### Microservices Architecture

**Intelligence Modules** (`com.ppc.Bot/intelligence/intelligence.py`):
- Event-driven services extending the `Intelligence` base class
- Two types:
  - **Location microservices**: Coordinate multiple devices across a location
  - **Device microservices**: Add features to specific device types

**index.py Pattern**:
- Each bot/package contains an `index.py` that registers microservices
- `MICROSERVICES["DEVICE_MICROSERVICES"]` dict maps device type integers to lists of `{"module": ..., "class": ...}` entries
- `MICROSERVICES["LOCATION_MICROSERVICES"]` list registers location-wide services
- index.py files are merged across packages when the bot is generated

**Signals** (`com.ppc.Bot/signals/`):
- Inter-microservice communication via internal data stream messages
- One-way communication pattern using signal interface files; receivers implement `datastream_updated(botengine, address, content)`

**Filters** (`com.ppc.Bot/filters/filter.py`):
- Data filtration layer that can modify device measurements before reaching microservices (`filter_measurements()`, `async_data_request_ready()`)
- Useful for data correction/normalization

### Event Flow
1. Bot triggered by device data, timers, schedules, etc.
2. `bot.run()` loads Controller from memory
3. Controller synchronizes devices and locations
4. `new_version()` called if bot version changed
5. `initialize()` called on every execution
6. Event-specific methods called on microservices (e.g., `device_measurements_updated()`, `timer_fired()`, `mode_updated()`, `question_answered()`)

### Key Files

- `structure.json`: Bot composition — `extends`, `microservices` (paths to shared packages copied into `intelligence/`), `safe_delete_microservices` (remove a package without resetting live bot instances), `pip_install` (pure-Python deps), `pip_install_remotely` (deps compiled on the Linux server; note the 50MB compressed / 250MB uncompressed bot size limit)
- `runtime.json`: Bot version, trigger types, schedules, device subscriptions, execution `timeout` (max 300s), and `runtime` Python version code (3.10=4, 3.11=5, 3.12=6, 3.13=7, 3.14=8)
- `index.py`: Microservice registration
- `properties.py` / `domain.py`: `get_property(botengine, name)` resolves organization-level property overrides first, then falls back to `domain.py` attributes — orgs can reconfigure a bot without code changes
- `.botignore`: Files/patterns excluded when generating the bot for deployment (tests, `__pycache__`, localization sources, etc.)

### BotEngine API

Located in `src/botengine/botengine.py`:
- Provides the interface to cloud services
- Handles device commands, timers, data requests, notifications, variable storage (persistent memory), questions
- Passed as first argument to all microservice methods
- `src/lambda.py` is the AWS Lambda entry point; `src/botengine_pytest/` is the test stub

### Time Utilities

Constants in `com.ppc.Bot/utilities/utilities.py`:
- `ONE_SECOND_MS`, `ONE_MINUTE_MS`, `ONE_HOUR_MS`, `ONE_DAY_MS`, `ONE_WEEK_MS`
- Mode constants: `MODE_HOME`, `MODE_AWAY`, `MODE_STAY`, `MODE_TEST`
- Occupancy states: `OCCUPANCY_STATUS_PRESENT`, `OCCUPANCY_STATUS_ABSENT`, etc.

## Creating a New Bot

1. Create a new directory `com.yourcompany.YourBot/` (or scaffold with `botlab init agent`)
2. Add `structure.json` with `"extends": "com.ppc.Bot"`
3. Create `intelligence/` directory with microservices
4. Add `index.py` to register microservices
5. Optionally add `runtime.json` for triggers and schedules

## Lessons

The `com.ppc.Lesson0-*` through `com.ppc.Lesson21-*` directories are progressive tutorial bots (microservices, commands, notifications, data streams, machine learning, questions, analytics, rules, edge computing, etc.). Each contains its own documentation — use them as reference implementations for framework features.
