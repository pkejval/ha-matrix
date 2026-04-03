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
- Create UI entities per room:
  - `text` for the outgoing draft message
  - `button` to send the current draft
  - `sensor` with the last Matrix event and payload

## Installation

Install this repository through HACS as a custom integration.

Note: this first version is for non-encrypted rooms. End-to-end encryption support can be added later if you need it.

## Configuration

Create one config entry per Matrix server.

The room field accepts room IDs or aliases separated by new lines, commas, or semicolons.

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

- a text entity for composing the message
- a button entity that sends the current draft
- a sensor entity that tracks the latest event for that room

The button sends the current text draft for the same room. After sending, the draft is cleared.

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
