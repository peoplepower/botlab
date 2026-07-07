# Organization Billing Microservice

## Overview

The Organization Billing Microservice automates billing calculations for multi-tenant organizations by identifying and counting billable devices across all subscriber locations. It provides administrators with accurate device counts for invoice generation based on actual device activity.

## Purpose

In multi-tenant scenarios, organizations need to:
- Track active devices across multiple subscriber locations
- Bill subscribers based on the number of connected devices
- Identify devices that are actually in use versus dormant devices
- Generate periodic billing reports

This microservice automates these tasks by querying device data across the organization and applying business rules to determine which devices should be included in billing calculations.

## How It Works

### Workflow

1. **Trigger**: An administrator or scheduled task sends a `calculate_invoice` data stream message to the organization
2. **Data Collection**: The microservice requests comprehensive location and device data from the organization
3. **Device Analysis**: Asynchronously processes all devices to identify billable ones based on:
   - Device type (must be in the billable device types list)
   - Recent activity (must have been online within the past 3 weeks)
4. **Report Generation**: Counts total billable devices and generates a report
5. **Notification**: Emails the billing summary to administrators

### Billable Device Types

The following device types are included in billing calculations:

| Device Type | Description |
|-------------|-------------|
| 31 | Camera devices |
| 32 | Gateway devices |
| 36 | Advanced camera devices |
| 37 | Advanced gateway devices |
| 10031 | Enterprise camera devices |
| 40 | Other billable devices |

### Activity Requirements

A device is only considered billable if:
- It matches one of the billable device types above
- It has a non-empty `measure_time` field
- Its last activity was within the past 3 weeks (21 days)

This ensures that organizations are only billed for devices that are actively in use.

## Data Stream Messages

### calculate_invoice

Triggers an invoice calculation for the organization.

**Address**: `calculate_invoice`

**Content**: Empty dictionary `{}`

**Scope**: Organization (scope=2)

**Example**:
```python
botengine.send_datastream_message("calculate_invoice", {}, scope=2)
```

## Data Requests

The microservice uses asynchronous data requests to gather information:

### Locations Request
- **Type**: `DATA_REQUEST_TYPE_LOCATIONS`
- **Reference**: `locations`
- **Purpose**: Retrieve all locations within the organization

### Devices Request
- **Type**: `DATA_REQUEST_TYPE_DEVICES`
- **Reference**: `devices`
- **Purpose**: Retrieve all devices across all locations with their metadata

## Tools

The `/tools` directory contains command-line utilities for interacting with this microservice:

### calculate_invoice.py

Sends a data stream message to trigger invoice calculation for an organization.

**Usage**:
```bash
python calculate_invoice.py \
  --admin_username admin@example.com \
  --admin_password your_password \
  -o 123 \
  -s app.peoplepowerco.com
```

**Arguments**:
- `--admin_username`: Administrator username for authentication
- `--admin_password`: Administrator password
- `-o, --organization_id`: Organization ID to calculate billing for (required)
- `-a, --apikey`: Optional API key (if not provided, will login with username/password)
- `-s, --server`: Server URL (default: https://app.peoplepowerco.com)
- `--httpdebug`: Enable HTTP debug logging

## Output

The microservice generates log entries showing:
- Each billable device identified with its metadata
- Total count of billable devices
- Organization ID and calculation timestamp

Example output:
```
Billable device: {'device_id': '123', 'device_type': 31, 'measure_time': 1704067200000, ...}
Billable device: {'device_id': '456', 'device_type': 32, 'measure_time': 1704153600000, ...}
TOTAL BILLABLE DEVICES: 15
```

An email is sent to administrators with the billing summary.

## Integration

### Scheduled Billing

To run automatic billing calculations, add a schedule to your `runtime.json`:

```json
{
  "schedules": [
    {
      "schedule_id": 1,
      "description": "Monthly billing calculation",
      "cron": "0 0 1 * * ?"
    }
  ]
}
```

Then implement the `schedule_fired()` method to trigger the calculation.

### Manual Trigger

From another microservice or bot:
```python
botengine.send_datastream_message("calculate_invoice", {}, scope=2, organization_id=org_id)
```

## Security Considerations

- Requires admin-level API key for command-line tool access
- Operates at organization scope (scope=2)
- Only processes devices that the organization has access to
- Email notifications sent only to configured administrator addresses

## Customization

To modify billing logic, edit these sections in `organization_billing_microservice.py`:

1. **BILLABLE_DEVICE_TYPES**: Update the list of device types that should be billed
2. **Activity Window**: Change `utilities.ONE_WEEK_MS * 3` to adjust the required activity window
3. **Email Recipients**: Modify the `email_addresses` parameter in `botengine.email_admins()`
4. **Additional Criteria**: Add custom filtering logic in the `async_data_request_ready()` method

## Dependencies

- `utilities.utilities`: Provides time constants (ONE_WEEK_MS)
- `intelligence.intelligence`: Base Intelligence class
- `bot`: Bot framework

## Notes

- This microservice executes asynchronously when processing data requests
- Class variables cannot be modified during async operations
- To return to synchronous execution, use `botengine.async_execute_again_in_n_seconds()`
- Device data structure depends on the platform's device API response format


