# Matrix Rooms

Custom Home Assistant integration for Matrix rooms with UI config flow support.

This is a maintained replacement for the official Home Assistant `matrix` integration, which is now effectively outdated for this use case.

The integration uses the `matrix_rooms` domain so it does not clash with the built-in Home Assistant `matrix` integration.

## Features

- Multiple Matrix servers, each as its own config entry
- Per-entry homeserver, username, password, and `verify_ssl`
- Optional per-entry global seen event emission
- Room list per server
- Send plain text messages to Matrix rooms
- Fire Home Assistant events for:
  - `matrix_rooms_received_new_msg`
  - `matrix_rooms_seen`
  - `matrix_rooms_any_seen`
  - `matrix_rooms_sent_msg`
  - `matrix_rooms_last_message_updated`
  - `matrix_rooms_last_seen_updated`
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
- `msgtype`
- `url`
- `event_id`
- `timestamp`

### `matrix_rooms_seen`

- `entry_id`
- `homeserver`
- `room_id`
- `room_name`
- `message_id`
- `message`
- `message_sender`
- `message_sender_name`
- `message_msgtype`
- `message_url`
- `message_timestamp`
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
- `msgtype`
- `url`
- `event_id`
- `timestamp`

### `matrix_rooms_last_message_updated`

- `entry_id`
- `homeserver`
- `room_id`
- `room_name`
- `message`
- `msgtype`
- `url`
- `sender`
- `sender_name`
- `self`
- `event_id`
- `timestamp`

### `matrix_rooms_last_seen_updated`

- `entry_id`
- `homeserver`
- `room_id`
- `room_name`
- `message_id`
- `message`
- `message_sender`
- `message_sender_name`
- `message_msgtype`
- `message_url`
- `message_timestamp`
- `seen_by`
- `seen_by_name`
- `self`
- `event_id`
- `receipt_type`
- `thread_id`
- `timestamp`

### `matrix_rooms_any_seen`

Emitted only when `Emit global seen events` is enabled for that Matrix server in the HA options UI.

Payload matches `matrix_rooms_seen`.

### Sensor states

- `Last message` starts with `waiting for message`
- `Last seen` starts with `waiting for receipt`

`Last message` tracks any `m.room.message` subtype, including images, files, audio, and video.
`matrix_rooms_seen` and `matrix_rooms_any_seen` include the seen message details when available.

## Automation examples

### Send event

```yaml
alias: Matrix sent message log
trigger:
  - platform: event
    event_type: matrix_rooms_sent_msg
action:
  - service: logbook.log
    data:
      name: Matrix
      message: "{{ trigger.event.data.sender_name }} sent '{{ trigger.event.data.message }}' to {{ trigger.event.data.room_name }}"
```

### Last message update

```yaml
alias: Matrix last message alert
trigger:
  - platform: event
    event_type: matrix_rooms_last_message_updated
action:
  - service: persistent_notification.create
    data:
      title: "Matrix message"
      message: "{{ trigger.event.data.room_name }}: {{ trigger.event.data.sender_name }} -> {{ trigger.event.data.message }}"
```

### Last seen update

```yaml
alias: Matrix read receipt
trigger:
  - platform: event
    event_type: matrix_rooms_last_seen_updated
action:
  - service: logbook.log
    data:
      name: Matrix
      message: "{{ trigger.event.data.room_name }} seen by {{ trigger.event.data.seen_by_name }}"
```

### Global seen event

```yaml
alias: Matrix any room seen
trigger:
  - platform: event
    event_type: matrix_rooms_any_seen
action:
  - service: persistent_notification.create
    data:
      title: "Matrix seen"
      message: "{{ trigger.event.data.seen_by_name }} saw a message in {{ trigger.event.data.room_name }}: {{ trigger.event.data.message }}"
```
