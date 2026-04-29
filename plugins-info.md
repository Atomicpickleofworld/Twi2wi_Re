# 🧩 Twi2wi_Re: Plugin Developer's Guide

> **API Version:** 1.0 (Subprocess Isolation)

## 🔒 Security Architecture (Important!)

Plugins in Twi2wi_Re operate not as a library within the program, but as **isolated processes (Subprocess)**.

✅ **What a plugin can do:**
* Read application configs (via API).
* Log its actions.
* Send notifications to the UI.
* Handle events (Connection, Disconnection, Log).

❌ **What a plugin can't do (Blocked):**
* `import os`, `import sys`, `import socket`
* `import requests`, `import urllib` (No network access!)
* `open()` outside its folder.
* Read/write Windows/Linux files.

## 📁 Plugin Structure

Create a `my_plugin` folder and two files in it:

```text
plugins/my_plugin/
├── plugin.json # ← Plugin Passport
└── main.py # ← Plugin Code
```

### 1. `plugin.json`

```json
{
"id": "my_plugin_unique_id",
"name": "My Super Plugin",
"version": "1.0.0",
"entry": "main.py",
"permissions": [
"hooks:read",
"notify:ui",
"log:read"
]
}
```

**Available Permissions:**
* `hooks:read` — (Required) Allows receiving events from the application.
* `notify:ui` — Enables pop-up notifications.
* `log:read` — Enables reading connection logs.
* `network:http` — *(Reserved, not currently supported due to isolation)*.

### 2. `main.py`

Your plugin receives the `ctx` (Context) object as the first argument to all functions.

```python
# plugins/my_plugin/main.py

# 1. Plugin startup event
def on_load(ctx):
ctx.log("Plugin started! 🚀")

# 2. VPN connection event
def on_connect(ctx, payload):
# payload contains {'config': {...}}
server = payload.get('config', {}).get('outbounds', [{}])[0].get('server', 'Unknown')
ctx.log(f"Connected to: {server}")

# If the 'notify:ui' permission is present, a notification can be shown
ctx.notify(f"Successfully connected to {server}")

# 3. Disconnect event
def on_disconnect(ctx, payload):
ctx.log("Connection terminated.")

# 4. Reading logs in real time
def on_log(ctx, payload):
line = payload.get('line', '')
# You can filter logs (e.g., look for errors)
if "error" in line.lower():
ctx.log(f"[Plugin] Error detected in log: {line}")

# 5. Plugin close event
def on_unload(ctx):
ctx.log("Plugin is unloading. Bye!")
```

## 🛠 Plugin API (`ctx` Object)

| Method | Description | Example |
| :--- | :--- | :--- |
| `ctx.log(msg)` | Writes to the application log with the plugin prefix | `ctx.log("Hello")` |
| `ctx.notify(msg)` | Shows a popup window (requires permissions) | `ctx.notify("Success!")` |
| `ctx.get_config()` | *(Under development)* Gets the current configuration | `conf = ctx.get_config()` |

## 📦 How to install?

1. Pack the plugin folder into a **ZIP archive** (the root of the archive must contain `plugin.json`).
2. In the app, click **Plugins** -> **Import from ZIP**.
3. Select the file. The app will check for security and launch the plugin.

---
*Developed for Twi2wi_Re. Unauthorized access to the system through plugins is impossible.*