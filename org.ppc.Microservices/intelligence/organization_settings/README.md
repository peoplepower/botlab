# Organization Settings Microservice

## Overview

The Organization Settings Microservice provides centralized configuration management for multi-location organizations. It enables administrators to define, distribute, and maintain global settings that are automatically synchronized across all bot instances within an organization.

## Purpose

Organizations with multiple locations face the challenge of maintaining consistent configuration across all their deployments. This microservice solves this by:

- Providing a single source of truth for organization-wide settings
- Automatically distributing settings to all bot instances
- Persisting settings for durability across system restarts
- Enforcing security to prevent unauthorized modifications
- Supporting dynamic configuration updates without redeployment

## How It Works

### Architecture

The microservice maintains an in-memory dictionary of settings (`self.settings`) and synchronizes them with persistent storage. Each setting is identified by a unique address (key) and contains arbitrary JSON-compatible data.

### Workflow

1. **Save Setting**: Administrator sends a `save_settings` message with the setting data
2. **Validation**: Microservice validates the request and checks for proper authorization
3. **Storage**: Setting is saved to the in-memory dictionary
4. **Persistence**: Setting is persisted via `botengine.set_admin_content()`
5. **Distribution**: Setting is broadcast to all bot instances in the organization
6. **Notification**: Confirmation is logged

### Security Model

The microservice implements security checks to prevent unauthorized modifications:

- Only requests originating directly from administrators are accepted
- Requests from other bot instances (`from_bot_id is not None`) are rejected
- All modifications are logged with security warnings for attempted violations

## Data Stream Messages

### save_settings

Saves or updates an organization-wide setting.

**Address**: `save_settings`

**Content**:
```json
{
  "address": "setting_name",
  "key1": "value1",
  "key2": "value2",
  ...
}
```

**Scope**: Organization (scope=2)

**Required Fields**:
- `address`: Unique identifier for the setting (will be removed from content and used as the key)

**Behavior**:
- Creates a new setting if it doesn't exist
- Updates an existing setting if the address already exists
- Distributes the setting to all bot instances
- Persists the setting for durability

### delete_settings

Removes an organization-wide setting.

**Address**: `delete_settings`

**Content**:
```json
{
  "address": "setting_name"
}
```

**Scope**: Organization (scope=2)

**Required Fields**:
- `address`: Unique identifier of the setting to delete

**Behavior**:
- Removes the setting from in-memory storage
- Deletes the setting from persistent storage
- Logs the deletion

### get_settings

Retrieves all organization settings for a specific bot instance.

**Address**: `get_settings`

**Content**: Empty or arbitrary (not used)

**Scope**: Organization (scope=2)

**Behavior**:
- Logs all current settings
- Sends each setting individually to the requesting bot instance
- Requires the sender's `bot_id` to deliver settings

## Tools

The `/tools` directory contains command-line utilities for managing organization settings:

### save_settings.py

Saves or updates an organization setting.

**Usage**:
```bash
python save_settings.py \
  --admin_username admin@example.com \
  --admin_password your_password \
  -o 123 \
  -s app.peoplepowerco.com
```

**Configuration**:
Edit the script to modify:
- `setting_name`: The address/key for the setting
- `setting_value`: The dictionary of configuration data

**Default Example**: The script includes a comprehensive Time-of-Use (TOU) pricing schedule with seasonal and daily rate tiers.

### delete_settings.py

Removes an organization setting.

**Usage**:
```bash
python delete_settings.py \
  --admin_username admin@example.com \
  --admin_password your_password \
  -o 123 \
  -s app.peoplepowerco.com
```

**Configuration**:
Edit the script to set `setting_name` to the address of the setting you want to delete.

### get_settings.py

Retrieves and displays all current organization settings.

**Usage**:
```bash
python get_settings.py \
  --admin_username admin@example.com \
  --admin_password your_password \
  -o 123 \
  -s app.peoplepowerco.com
```

**Common Arguments** (all tools):
- `--admin_username`: Administrator username for authentication
- `--admin_password`: Administrator password
- `-o, --organization_id`: Organization ID (required)
- `-a, --apikey`: Optional API key (if not provided, will login)
- `-s, --server`: Server URL (default: https://app.peoplepowerco.com)
- `--httpdebug`: Enable HTTP debug logging

## Common Use Cases

### Time-of-Use (TOU) Rate Schedules

Define electricity pricing schedules that vary by time of day, day of week, and season:

```json
{
  "address": "tou_schedule",
  "summer_weekday_high_schedule": "0 0 13 ? MAY-OCT MON-FRI *",
  "summer_weekday_high_tier": 2,
  "summer_weekday_high_description": "Summer Peak Pricing",
  ...
}
```

Bot instances can use these schedules to optimize energy usage during off-peak hours.

### Feature Flags

Enable or disable features across the organization:

```json
{
  "address": "feature_flags",
  "advanced_analytics_enabled": true,
  "beta_features_enabled": false,
  "ml_predictions_enabled": true
}
```

### Operational Parameters

Define organization-wide operational thresholds:

```json
{
  "address": "operational_params",
  "alert_threshold_temperature": 85,
  "motion_sensitivity": "medium",
  "reporting_interval_minutes": 15
}
```

### Custom Configurations

Store any organization-specific configuration:

```json
{
  "address": "custom_config",
  "company_name": "Acme Corp",
  "timezone": "America/New_York",
  "business_hours_start": "08:00",
  "business_hours_end": "18:00"
}
```

## Integration

### Receiving Settings in Bot Instances

In your bot instance, implement a method matching the setting address:

```python
def tou_schedule(self, botengine, content):
    """
    Receive TOU schedule settings
    :param botengine: BotEngine environment
    :param content: Setting content
    """
    botengine.get_logger().info("Received TOU schedule: {}".format(content))
    self.apply_tou_schedule(botengine, content)
```

The `datastream_updated()` method automatically routes messages to methods matching the address.

### Requesting Settings

When a bot instance starts, it can request all current settings:

```python
botengine.send_datastream_message("get_settings", {}, scope=1, bot_instance_list=[my_bot_id])
```

### Updating Settings

From an administrative interface or script:

```python
content = {
    "address": "my_setting",
    "value1": "data1",
    "value2": "data2"
}
botengine.send_datastream_message("save_settings", content, scope=2, organization_id=org_id)
```

## Data Storage

### In-Memory Storage

Settings are stored in `self.settings` dictionary:
```python
{
  "tou_schedule": {"summer_weekday_high_tier": 2, ...},
  "feature_flags": {"advanced_analytics_enabled": true, ...},
  ...
}
```

### Persistent Storage

Settings are persisted using:
```python
botengine.set_admin_content(organization_id, address, settings)
```

To delete:
```python
botengine.delete_admin_content(organization_id, address)
```

## Security Considerations

### Authentication
- Command-line tools require admin-level authentication
- API keys are cached locally for convenience (stored as pickle files)
- Two-factor authentication is supported via passcode prompts

### Authorization
- Settings can only be modified via direct administrative requests
- Bot instances cannot modify organization settings (prevented via `from_bot_id` checks)
- All unauthorized attempts are logged as security warnings

### Scope
- Settings are distributed at organization scope (scope=1 for distribution, scope=2 for incoming)
- Only bot instances within the organization receive the settings
- Settings are isolated between organizations

## Best Practices

1. **Naming Convention**: Use descriptive, hierarchical addresses (e.g., `energy.tou_schedule`, `alerts.temperature_threshold`)
2. **Versioning**: Include version fields in settings to handle schema changes gracefully
3. **Documentation**: Document the structure and purpose of each setting
4. **Validation**: Validate setting content in receiving bot instances before applying
5. **Defaults**: Implement sensible defaults in case settings are missing
6. **Testing**: Test setting changes in a development organization before production deployment
7. **Monitoring**: Log setting changes and monitor for unexpected modifications

## Dependencies

- `intelligence.intelligence`: Base Intelligence class
- `bot`: Bot framework

## Troubleshooting

### Settings Not Received by Bot Instances

1. Verify the bot instance is running and listening for data stream messages
2. Check that the bot instance implements a method matching the setting address
3. Ensure the bot instance is part of the organization
4. Review logs for data stream message delivery

### Settings Not Persisting

1. Verify `botengine.set_admin_content()` is called successfully
2. Check for errors in persistence layer
3. Ensure organization ID is valid

### Unauthorized Modification Attempts

If you see security warnings about unauthorized bot attempts to modify settings:
1. Review which bots are attempting modifications
2. Ensure proper separation between administrative tools and bot instances
3. Verify that bots are not incorrectly relaying administrative commands

## Notes

- Settings are JSON-compatible (strings, numbers, booleans, arrays, objects)
- The `address` field is special: it's removed from content and used as the dictionary key
- Settings are distributed individually when requested via `get_settings`
- This microservice does not validate setting content; validation should occur in receiving bot instances
- The example TOU schedule in `save_settings.py` demonstrates a complex real-world configuration


