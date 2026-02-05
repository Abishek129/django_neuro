# django_neuro (OS Backend) - API Documentation

## Overview

System management backend providing hardware monitoring, power control, WiFi management, terminal access, and real-time resource metrics over WebSocket.

- **Framework**: Django, DRF, Django Channels
- **Authentication**: Keycloak JWT
- **Channel Layer**: Redis

---

## HTTP Endpoints

All routes are prefixed with `/api/`.

### WiFi Management (`/api/wifi/`)

| Method | Path | Name | Description |
|--------|------|------|-------------|
| GET | `/api/wifi/status` | `wifi-status` | Get WiFi status |
| GET | `/api/wifi/enabled` | `wifi-enabled` | Check if WiFi is enabled |
| POST | `/api/wifi/toggle` | `wifi-toggle` | Toggle WiFi on/off |
| GET | `/api/wifi/networks` | `wifi-networks` | Scan available networks |
| GET | `/api/wifi/current` | `wifi-current` | Get current connected network |
| POST | `/api/wifi/connect` | `wifi-connect` | Connect to a network |
| POST | `/api/wifi/disconnect` | `wifi-disconnect` | Disconnect from network |
| POST | `/api/wifi/forget` | `wifi-forget` | Forget a saved network |
| GET | `/api/wifi/saved-networks` | `wifi-saved-networks` | List saved networks |
| POST | `/api/wifi/reconnect` | `wifi-reconnect` | Reconnect to network |

### Sound Management (`/api/sound/`)

| Method | Path | Name | Description |
|--------|------|------|-------------|
| GET | `/api/sound/status` | `sound-status` | Get sound status |
| GET/POST | `/api/sound/volume` | `sound-volume` | Get/set volume |
| POST | `/api/sound/mute` | `sound-mute` | Mute audio |
| POST | `/api/sound/mute/toggle` | `sound-mute-toggle` | Toggle mute |
| GET | `/api/sound/devices` | `sound-devices` | List audio devices |
| POST | `/api/sound/device` | `sound-device` | Set audio device |

### Device Management (`/api/devices/`)

| Method | Path | Name | Description |
|--------|------|------|-------------|
| GET | `/api/devices/` | `devices` | List all devices |
| POST | `/api/devices/forget` | `devices-forget` | Forget a device |

### Power Management (`/api/power/`)

| Method | Path | Name | Description |
|--------|------|------|-------------|
| GET | `/api/power/status` | `power-status` | Get power status |
| POST | `/api/power/authenticate` | `power-auth` | Power authentication |
| POST | `/api/power/sleep` | `power-sleep` | Put system to sleep |
| POST | `/api/power/restart` | `power-restart` | Restart system |
| POST | `/api/power/shutdown` | `power-shutdown` | Shutdown system |

### Keycloak Authentication (`/api/keycloak/`)

| Method | Path | Name | Description |
|--------|------|------|-------------|
| POST | `/api/keycloak/login` | `keycloak-login` | User login |
| POST | `/api/keycloak/register` | `keycloak-register` | User registration |
| POST | `/api/keycloak/authenticate` | `keycloak-authenticate` | Authenticate user |

### Terminal (`/api/terminal/`)

| Method | Path | Name | Description |
|--------|------|------|-------------|
| GET | `/api/terminal/sessions` | `terminal-sessions` | List terminal sessions |

### Control Panel (`/api/control/`)

| Method | Path | Name | Description |
|--------|------|------|-------------|
| POST | `/api/control/test-ws` | `control-test-ws` | Test WebSocket message |
| POST | `/api/control/groups` | `control-create-group` | Create user group |
| GET | `/api/control/users` | `control-list-users` | List users |
| GET | `/api/control/roles` | `control-list-roles` | List roles |
| GET | `/api/control/users/by-roles` | `control-users-by-roles` | List users by roles |
| POST | `/api/control/groups/add-user` | `control-add-user-to-group` | Add user to group |
| POST | `/api/control/groups/add-roles` | `control-add-roles-to-group` | Add roles to group |
| POST | `/api/control/notifications` | `control-notifications-create` | Create notification |
| GET | `/api/control/notifications/me` | `control-notifications-me` | Get user notifications |

### Task Manager - CPU (`/api/task/cpu/`)

| Method | Path | Name | Description |
|--------|------|------|-------------|
| GET | `/api/task/cpu/status` | `cpu-status` | Get CPU status |
| GET | `/api/task/cpu/history` | `cpu-history` | Get CPU history |
| GET | `/api/task/cpu/breakdown` | `cpu-breakdown` | Get per-core breakdown |
| GET | `/api/task/cpu/processes` | `cpu-processes` | Get top CPU processes |

### Task Manager - Memory (`/api/task/memory/`)

| Method | Path | Name | Description |
|--------|------|------|-------------|
| GET | `/api/task/memory/status` | `memory-status` | Get memory status |
| GET | `/api/task/memory/history` | `memory-history` | Get memory history |
| GET | `/api/task/memory/breakdown` | `memory-breakdown` | Get memory breakdown |
| GET | `/api/task/memory/processes` | `memory-processes` | Get top memory processes |

### Task Manager - GPU (`/api/task/gpu/`)

| Method | Path | Name | Description |
|--------|------|------|-------------|
| GET | `/api/task/gpu/status` | `gpu-status` | Get GPU status |
| GET | `/api/task/gpu/history` | `gpu-history` | Get GPU history |
| GET | `/api/task/gpu/breakdown` | `gpu-breakdown` | Get GPU breakdown |
| GET | `/api/task/gpu/processes` | `gpu-processes` | Get top GPU processes |

### Task Manager - Disk (`/api/task/disk/`)

| Method | Path | Name | Description |
|--------|------|------|-------------|
| GET | `/api/task/disk/status` | `disk-status` | Get disk status |
| GET | `/api/task/disk/history` | `disk-history` | Get disk history |
| GET | `/api/task/disk/breakdown` | `disk-breakdown` | Get disk breakdown |
| GET | `/api/task/disk/processes` | `disk-processes` | Get top disk I/O processes |

### Task Manager - BMC (`/api/task/bmc/`)

| Method | Path | Name | Description |
|--------|------|------|-------------|
| GET | `/api/task/bmc/status` | `bmc-status` | Get BMC sensor status |
| GET | `/api/task/bmc/history` | `bmc-history` | Get BMC history |
| POST | `/api/task/bmc/history/clear` | `bmc-clear-history` | Clear BMC history |
| GET | `/api/task/bmc/live/` | - | Get live sensor data |
| GET | `/api/task/bmc/available/` | - | Get available sensors |
| GET | `/api/task/bmc/pwm/controls/` | - | Get PWM fan controls |
| POST | `/api/task/bmc/pwm/set-value/` | - | Set PWM value |
| POST | `/api/task/bmc/pwm/set-mode/` | - | Set PWM mode |
| GET | `/api/task/bmc/ipmi/status/` | - | Get IPMI status |
| GET | `/api/task/bmc/ipmi/sensors/` | - | Get IPMI sensors |
| GET | `/api/task/bmc/ipmi/chassis/` | - | Get IPMI chassis info |
| GET | `/api/task/bmc/ipmi/sel/` | - | Get IPMI system event log |
| GET | `/api/task/bmc/system/info/` | - | Get system info |
| GET | `/api/task/bmc/system/power/` | - | Get system power status |
| GET | `/api/task/bmc/raw/` | - | Get raw sensor data |

### Task Manager - Events (`/api/task/events/`)

| Method | Path | Name | Description |
|--------|------|------|-------------|
| GET | `/api/task/events/` | `events` | Get system events |

---

## WebSocket Endpoints

### Terminal

| Route | Consumer | Auth | Description |
|-------|----------|------|-------------|
| `api/terminal/ws/` | `TerminalConsumer` | - | Interactive shell (new session) |
| `api/terminal/ws/<session_id>/` | `TerminalConsumer` | - | Interactive shell (resume session) |

**File**: `terminal_api/consumers.py`

**Message types** (client to server):
- `input` - Send text input to the shell
- `resize` - Resize terminal (`{type: "resize", rows: N, cols: N}`)

**Message types** (server to client):
- `output` - Terminal output text
- `session` - Session ID confirmation
- `exit` - Shell exited

---

### Notifications

| Route | Consumer | Auth | Description |
|-------|----------|------|-------------|
| `api/control/notifications/ws/` | `NotificationConsumer` | Keycloak JWT | User-specific notifications |

**File**: `control_pannel/consumers.py`

**Behavior**:
- Requires Keycloak auth with `sub` claim (user UUID).
- Joins user-specific group: `notifications_{user_uuid}`.
- Receives `notification_message` events and forwards them to the client.
- Returns `4401` if unauthenticated.

---

### CPU Monitoring

| Route | Consumer | Description |
|-------|----------|-------------|
| `api/task/cpu/ws/` | `CpuMonitorConsumer` | Real-time CPU status |
| `api/task/cpu/status/ws/` | `CpuMonitorConsumer` | Alias for above |
| `api/task/cpu/history/ws/` | `CpuHistoryConsumer` | CPU history stream |
| `api/task/cpu/breakdown/ws/` | `CpuBreakdownConsumer` | Per-core breakdown stream |
| `api/task/cpu/processes/ws/` | `CpuProcessesConsumer` | Top CPU processes stream |

**Query params**: `interval` (1-60s, default 2s), `limit` (1-200, default 20)
**Runtime commands**: `set_interval`, `set_limit`

---

### Memory Monitoring

| Route | Consumer | Description |
|-------|----------|-------------|
| `api/task/memory/ws/` | `MemoryMonitorConsumer` | Real-time memory status |
| `api/task/memory/status/ws/` | `MemoryMonitorConsumer` | Alias for above |
| `api/task/memory/history/ws/` | `MemoryHistoryConsumer` | Memory history stream |
| `api/task/memory/breakdown/ws/` | `MemoryBreakdownConsumer` | Memory breakdown stream |
| `api/task/memory/processes/ws/` | `MemoryProcessesConsumer` | Top memory processes stream |

**Query params**: `interval` (1-60s, default 2s), `limit` (1-200, default 20)
**Runtime commands**: `set_interval`, `set_limit`

---

### GPU Monitoring

| Route | Consumer | Description |
|-------|----------|-------------|
| `api/task/gpu/ws/` | `GpuMonitorConsumer` | Real-time GPU status |
| `api/task/gpu/status/ws/` | `GpuMonitorConsumer` | Alias for above |
| `api/task/gpu/history/ws/` | `GpuHistoryConsumer` | GPU history stream |
| `api/task/gpu/breakdown/ws/` | `GpuBreakdownConsumer` | GPU breakdown stream |
| `api/task/gpu/processes/ws/` | `GpuProcessesConsumer` | Top GPU processes stream |

**Query params**: `interval` (1-60s, default 2s), `limit` (1-200, default 20)
**Runtime commands**: `set_interval`, `set_limit`

---

### Disk Monitoring

| Route | Consumer | Description |
|-------|----------|-------------|
| `api/task/disk/ws/` | `DiskMonitorConsumer` | Real-time disk status |
| `api/task/disk/status/ws/` | `DiskMonitorConsumer` | Alias for above |
| `api/task/disk/history/ws/` | `DiskHistoryConsumer` | Disk history stream |
| `api/task/disk/breakdown/ws/` | `DiskBreakdownConsumer` | Disk breakdown stream |
| `api/task/disk/processes/ws/` | `DiskProcessesConsumer` | Top disk I/O processes stream |

**Query params**: `interval` (1-60s, default 2s), `limit` (1-200, default 20)
**Runtime commands**: `set_interval`, `set_limit`

---

### BMC Monitoring

| Route | Consumer | Description |
|-------|----------|-------------|
| `api/task/bmc/ws/` | `BmcMonitorConsumer` | Real-time BMC/sensor status |
| `api/task/bmc/status/ws/` | `BmcMonitorConsumer` | Alias for above |
| `api/task/bmc/history/ws/` | `BmcHistoryConsumer` | BMC history stream |
| `api/task/bmc/breakdown/ws/` | `BmcBreakdownConsumer` | BMC breakdown stream |

**Query params**: `interval` (1-60s, default 5s for status, 2s for others)
**Runtime commands**: `set_interval`

---

### Events

| Route | Consumer | Description |
|-------|----------|-------------|
| `api/task/events/ws/` | `EventConsumer` | Real-time system events |

**Group**: `events` (broadcast to all connected clients)
**Message type**: `event_created`

---

### Unified Processes

| Route | Consumer | Description |
|-------|----------|-------------|
| `api/task/processes/ws/` | `UnifiedProcessesConsumer` | Aggregated top processes |

**Query params**: `interval` (1-60s, default 2s), `limit` (1-200, default 50)
**Runtime commands**: `set_interval`, `set_limit`

---

### Power

| Route | Consumer | Auth | Description |
|-------|----------|------|-------------|
| `api/power/ws/` | `PowerConsumer` | Keycloak JWT (`power_to_shut` role) | Power event updates |

**Group**: `power_updates`
**Message type**: `power_message`
**Auth errors**: `4401` (no auth), `4403` (missing role)

---

## Summary

| Category | Count |
|----------|-------|
| HTTP Endpoints | 65+ |
| WebSocket Consumers | 25 |
| Apps | 8 (wifi, sound, devices, power, keycloak_api, terminal_api, control_pannel, task_manager) |
| Task Manager Sub-apps | 6 (cpu, memory, gpu, disk, bmc, events) |

---

## Key Files

| File | Purpose |
|------|---------|
| `neuro_backend/urls.py` | Root URL configuration |
| `*/urls.py` | Per-app URL patterns |
| `*/routing.py` | Per-app WebSocket routing |
| `*/consumers.py` | Per-app WebSocket consumers |
| `neuro_backend/asgi.py` | ASGI protocol router |

---

## Frontend Mapping

The frontend lives at `/home/rohith/desktop/frontend/webshell-react` (React 19 + Vite). It connects to django_neuro on port `8000` for HTTP and WebSocket traffic.

### Connection Configuration

**Base API URL**: `http://{hostname}:8000` (configurable via `VITE_API_BASE`)

**Frontend service layer**: `src/services/api.js` provides `get()` and `post()` helpers used by all service modules. All requests use `Content-Type: application/json`.

### Frontend Service Files to Backend Endpoints

#### `src/services/wifiService.js` → `/api/wifi/*`

| Frontend Function | Method | Backend Endpoint | Request Body |
|-------------------|--------|------------------|--------------|
| `getWifiStatus()` | GET | `/api/wifi/status` | - |
| `isWifiEnabled()` | GET | `/api/wifi/enabled` | - |
| `setWifiEnabled(enabled)` | POST | `/api/wifi/toggle` | `{ enabled }` |
| `getNetworks()` | GET | `/api/wifi/networks` | - |
| `getCurrentConnection()` | GET | `/api/wifi/current` | - |
| `connectToNetwork(ssid, password)` | POST | `/api/wifi/connect` | `{ ssid, password? }` |
| `disconnect()` | POST | `/api/wifi/disconnect` | - |
| `forgetNetwork(ssid)` | POST | `/api/wifi/forget` | `{ ssid }` |

#### `src/services/soundService.js` → `/api/sound/*`

| Frontend Function | Method | Backend Endpoint | Request Body |
|-------------------|--------|------------------|--------------|
| `getSoundStatus()` | GET | `/api/sound/status` | - |
| `getVolume()` | GET | `/api/sound/volume` | - |
| `setVolume(volume)` | POST | `/api/sound/volume` | `{ volume }` |
| `getMute()` | GET | `/api/sound/mute` | - |
| `setMute(muted)` | POST | `/api/sound/mute` | `{ muted }` |
| `toggleMute()` | POST | `/api/sound/mute/toggle` | - |
| `getDevices()` | GET | `/api/sound/devices` | - |
| `setDevice(deviceName)` | POST | `/api/sound/device` | `{ device_name }` |

#### `src/services/devicesService.js` → `/api/devices/*`

| Frontend Function | Method | Backend Endpoint | Request Body |
|-------------------|--------|------------------|--------------|
| `getAllDevices()` | GET | `/api/devices/` | - |
| `getBluetoothDevices()` | GET | `/api/devices/bluetooth` | - |
| `scanBluetoothDevices()` | GET | `/api/devices/bluetooth/scan` | - |
| `connectBluetoothDevice(mac)` | POST | `/api/devices/bluetooth/connect` | `{ mac_address }` |
| `disconnectBluetoothDevice(mac)` | POST | `/api/devices/bluetooth/disconnect` | `{ mac_address }` |
| `forgetBluetoothDevice(mac)` | POST | `/api/devices/bluetooth/forget` | `{ mac_address }` |
| `getUsbDevices()` | GET | `/api/devices/usb` | - |
| `getInputDevices()` | GET | `/api/devices/input` | - |
| `forgetDevice(deviceId)` | POST | `/api/devices/forget` | `{ device_id }` |

Note: Bluetooth endpoints are currently commented out in the backend `devices/urls.py`.

#### `src/taskbar/taskManager/services/taskManagerApi.js` → `/api/task/*`

| Frontend Function | Method | Backend Endpoint | Query Params |
|-------------------|--------|------------------|--------------|
| `fetchCpuStatus()` | GET | `/api/task/cpu/status` | - |
| `fetchCpuHistory()` | GET | `/api/task/cpu/history` | - |
| `fetchCpuBreakdown()` | GET | `/api/task/cpu/breakdown` | - |
| `fetchCpuProcesses(limit)` | GET | `/api/task/cpu/processes` | `?limit={limit}` |
| `fetchEvents(options)` | GET | `/api/task/events/` | `?metric=&severity=&limit=` |

### Frontend WebSocket Connections to Backend

#### `src/hooks/useLoggerWebSocket.js` → LoggerDeploy backend

| WebSocket URL | Backend Consumer | Auth | Purpose |
|---------------|-----------------|------|---------|
| `ws://{host}/ws/logs/?token={jwt}` | `LoggerReadConsumer` (LoggerDeploy) | Keycloak JWT | Stream logger notifications to an embedded iframe |

Note: This connects to the **LoggerDeploy** backend, not django_neuro. Messages are forwarded to a Logger iframe via `postMessage`.

#### `src/taskbar/taskManager/services/websocketService.js` → Task Manager consumers

All connections use `ws://{hostname}:8000` as base URL.

**CPU** (`createCpuWebSocket()`):

| WebSocket URL | Backend Consumer | Message Type |
|---------------|-----------------|--------------|
| `/api/task/cpu/status/ws?interval=1` | `CpuMonitorConsumer` | `cpu_status` |
| `/api/task/cpu/history/ws?interval=1` | `CpuHistoryConsumer` | `cpu_history` |
| `/api/task/cpu/breakdown/ws?interval=1` | `CpuBreakdownConsumer` | `cpu_breakdown` |
| `/api/task/cpu/processes/ws?interval=1&limit=5` | `CpuProcessesConsumer` | `cpu_processes` |

**Memory** (`createMemoryWebSocket()`):

| WebSocket URL | Backend Consumer | Message Type |
|---------------|-----------------|--------------|
| `/api/task/memory/status/ws?interval=1` | `MemoryMonitorConsumer` | `memory_status` |
| `/api/task/memory/history/ws?interval=1` | `MemoryHistoryConsumer` | `memory_history` |
| `/api/task/memory/breakdown/ws?interval=1` | `MemoryBreakdownConsumer` | `memory_breakdown` |
| `/api/task/memory/processes/ws?interval=1&limit=5` | `MemoryProcessesConsumer` | `memory_processes` |

**GPU** (`createGpuWebSocket()`):

| WebSocket URL | Backend Consumer | Message Type |
|---------------|-----------------|--------------|
| `/api/task/gpu/status/ws?interval=1` | `GpuMonitorConsumer` | `gpu_status` |
| `/api/task/gpu/history/ws?interval=1` | `GpuHistoryConsumer` | `gpu_history` |
| `/api/task/gpu/breakdown/ws?interval=1` | `GpuBreakdownConsumer` | `gpu_breakdown` |
| `/api/task/gpu/processes/ws?interval=1&limit=5` | `GpuProcessesConsumer` | `gpu_processes` |

**Disk** (`createDiskWebSocket()`):

| WebSocket URL | Backend Consumer | Message Type |
|---------------|-----------------|--------------|
| `/api/task/disk/status/ws?interval=1` | `DiskMonitorConsumer` | `disk_status` |
| `/api/task/disk/history/ws?interval=1` | `DiskHistoryConsumer` | `disk_history` |
| `/api/task/disk/breakdown/ws?interval=1` | `DiskBreakdownConsumer` | `disk_breakdown` |
| `/api/task/disk/processes/ws?interval=1&limit=5` | `DiskProcessesConsumer` | `disk_processes` |

**BMC** (`createBmcWebSocket()`):

| WebSocket URL | Backend Consumer | Message Type |
|---------------|-----------------|--------------|
| `/api/task/bmc/status/ws?interval=2` | `BmcMonitorConsumer` | `bmc_status` |
| `/api/task/bmc/history/ws?interval=5` | `BmcHistoryConsumer` | `bmc_history` |
| `/api/task/bmc/breakdown/ws?interval=5` | `BmcBreakdownConsumer` | `bmc_breakdown` |

### React Context Providers (State Management Layer)

These contexts wrap the service calls and manage state for the UI:

| Context File | Service Used | Exposed Functions |
|-------------|-------------|-------------------|
| `src/contexts/NetworkContext.jsx` | `wifiService` | `toggleWifi()`, `connectToNetwork()`, `forgetNetwork()`, `disconnectNetwork()`, `refreshNetworks()`, `fetchWifiStatus()` |
| `src/contexts/DevicesContext.jsx` | `devicesService` | `fetchDevices()`, `scanBluetooth()`, `connectBluetooth()`, `disconnectBluetooth()`, `forgetBluetooth()`, `forgetDevice()`, `refreshDevices()` |
| `src/contexts/KeycloakContext.jsx` | Keycloak JS | Authentication state, JWT tokens for WebSocket auth |

### Data Flow

```
React Component
  → Context Provider (state management)
    → Service Module (src/services/*.js)
      → api.get() / api.post()
        → HTTP GET/POST to django_neuro port 8000

React Component (real-time)
  → websocketService factory (src/taskbar/taskManager/services/websocketService.js)
    → new WebSocket(ws://hostname:8000/api/task/...)
      → Django Channels consumer streams data back
```

### Backend Endpoints NOT Used by Frontend

The following backend endpoints exist but have no corresponding frontend call:

- `/api/wifi/saved-networks` - not called from any service
- `/api/wifi/reconnect` - not called from any service
- `/api/power/*` - power WebSocket (`api/power/ws/`) not connected from frontend
- `/api/control/*` - control panel endpoints (groups, roles, notifications) not called
- `/api/terminal/ws/` - terminal WebSocket exists in backend but frontend terminal integration uses xterm.js directly
- `/api/task/events/ws/` - events WebSocket consumer not connected
- `/api/task/processes/ws/` - unified processes WebSocket not connected
- All BMC IPMI/PWM/system HTTP endpoints - no frontend calls
- `/api/keycloak/*` - frontend uses Keycloak JS adapter directly, not these proxy endpoints
