# Matrix Rooms

Custom Home Assistant integration for Matrix rooms with UI config flow support.

The integration uses the `matrix_rooms` domain so it does not clash with the built-in Home Assistant `matrix` integration.

## Features

- Multiple Matrix servers, each as its own config entry
- Per-entry homeserver, username, password, and `verify_ssl`
- Room list per server
- Send plain text messages to Matrix rooms
- Fire Home Assistant events for:
  - `matrix_rooms_received_new_msg`
  - `matrix_rooms_seen`
  - `matrix_rooms_sent_msg`
- Create UI entities per room:
  - `sensor` for the last message
  - `sensor` for the last seen receipt

## Installation

Install this repository through HACS as a custom integration.

Note: this first version is for non-encrypted rooms. End-to-end encryption support can be added later if you need it.

## Configuration

Create one config entry per Matrix server.

Rooms are added one by one in the UI flow. Enter either a room ID like `!abcdef:example.org` or an alias like `#alerts:example.org`, then choose whether to add another room or finish.

Example:

```text
!abcdef:example.org
#alerts:example.org
```

## Service

`matrix_rooms.send_message`

Required fields:

- `room_id`
- `message`

Optional field:

- `entry_id`

If you have configured only one Matrix server, `entry_id` can be omitted.

## Entities

For each configured room, the integration creates:

- a sensor entity that tracks the latest message for that room
- a sensor entity that tracks the latest seen receipt for that room

## Event payloads

### `matrix_rooms_received_new_msg`

- `entry_id`
- `homeserver`
- `room_id`
- `room_name`
- `sender`
- `sender_name`
- `self`
- `message`
- `event_id`
- `timestamp`

### `matrix_rooms_seen`

- `entry_id`
- `homeserver`
- `room_id`
- `room_name`
- `seen_by`
- `seen_by_name`
- `self`
- `event_id`
- `receipt_type`
- `thread_id`
- `timestamp`

### `matrix_rooms_sent_msg`

- `entry_id`
- `homeserver`
- `room_id`
- `room_name`
- `sender`
- `sender_name`
- `self`
- `message`
- `event_id`
- `timestamp`

### Sensor states

- `Last message` starts with `waiting for message`
- `Last seen` starts with `waiting for receipt`
