# Visitors Microservice

Consolidated visitor tracking microservice that receives visitor detection signals from multiple sources (radar, motion sensors) and manages trends, dashboard service cards, and daily report entries.

## Architecture

```
Detection Layer (unchanged):
  └── radar/location_radarvisitor_microservice.py - Radar-based detection engine
                     │
                     ▼ emits signals
Signals Layer:
  └── signals/visitor/ - Clean visitor signals interface
                     │
                     ▼ received by
Service Layer:
  └── visitors/location_visitor_microservice.py - Consolidation & management
                     │
                     ▼ integrates with
Integration Layer:
  ├── signals/trends.py - Trend capture
  ├── signals/dailyreport.py - Report entries
  └── signals/dashboard.py - Service cards
```

## Signal Handlers

The microservice implements handlers for visitor detection signals:

- `did_start_detecting_visitor(botengine)` - 2+ people reliably detected in home
- `did_stop_detecting_visitor(botengine)` - 1 or fewer people detected
- `did_start_detecting_together(botengine)` - 2+ people in same room
- `did_stop_detecting_together(botengine)` - No 2+ people in same room
- `did_log_visitor_event(botengine, event)` - Real-time event logging
- `did_log_visitor_events(botengine, events)` - Batch events at midnight

## Visitor Event Structure

```python
{
    "timestamp_ms": int,      # Event timestamp
    "device_id": str|None,    # Source device ID
    "room_name": str|None,    # Room where event occurred
    "event": str,             # "visitor_start"|"visitor_stop"|"together_start"|"together_stop"
    "duration_ms": int|None,  # Duration for stop events
    "source": str|None        # "radar"|"motion"|"manual"
}
```

## Trends Captured

| Trend ID | Category | Operation | Description |
|----------|----------|-----------|-------------|
| `trend.visitor` | SOCIAL | ACCUMULATE | Total visitor duration (ms) |
| `trend.together` | SOCIAL | ACCUMULATE | Total together-in-room time (ms) |
| `trend.visitor_count` | SOCIAL | ACCUMULATE | Number of visitor events |

## Service Settings

| Key | Type | Purpose |
|-----|------|---------|
| `care.visitors` | Boolean | Enable/disable visitor tracking |
| `care.visitoralerts` | Boolean | Enable/disable push notifications |
| `care.visitoralerttimeout` | Integer | Alert auto-clear timeout (minutes) |

## Dependencies

- `intelligence/daylight` - Midnight schedule

## Dependencies (optional)

- `intelligence/trends` - Trend capture
- `intelligence/dailyreport` - Daily report entries
- `intelligence/dashboard` - Service card management

## Testing

```bash
./pytest --mut visitors
```
