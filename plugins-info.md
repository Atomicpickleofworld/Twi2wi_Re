# 🧩 Twi2wi_Re: Plugin Developer's Guide

> **API Version:** 1.0 (Subprocess Isolation)  
> **Status:** UI & Tabs are **Beta** (experimental)

## 🔒 Security Architecture (Important!)

Plugins in Twi2wi_Re operate not as a library within the program, but as **isolated processes (Subprocess)**.  
The host application communicates with plugins strictly via `stdin`/`stdout` JSON streams.

✅ **What a plugin can do:**
* Handle app events (Connection, Ping, Logs, Config changes).
* Create custom tabs in the sidebar with HTML/CSS content.
* Patch application styles (experimental).
* Log its actions & send UI notifications.

 **What a plugin can't do (Hard Blocked):**
* `import os`, `import sys`, `import socket`, `import requests`
* `open()` outside its own `plugins/<id>/` folder.
* Execute external processes or access the network directly.
* Inject JavaScript or bypass the HTML sanitizer.

---

## 📁 Plugin Structure

Create a folder with a unique ID and two files inside:

```text
plugins/my_plugin/
├── plugin.json  # ← Manifest & Permissions
└── main.py      # ← Plugin Logic
```

### 1. `plugin.json`

```json
{
  "id": "my_plugin_unique_id",
  "name": "My Super Plugin",
  "version": "1.0.0",
  "entry": "main.py",
  "description": "Adds a custom tab and tracks connections",
  "permissions": [
    "hooks:read",
    "notify:ui",
    "ui:tab",
    "ui:style"
  ]
}
```

**Available Permissions:**
| Permission | Description |
|------------|-------------|
| `hooks:read` | **(Required)** Allows receiving events from the application. |
| `notify:ui` | Enables pop-up notifications in the host UI. |
| `ui:tab` | Allows registering a custom sidebar tab. |
| `ui:style` | Allows patching global app CSS (experimental). |
| `network:http` | *(Reserved)* Not yet supported due to sandbox isolation. |

### 2. `main.py`

Your plugin receives the `ctx` (PluginContext) object as the first argument to all hooks.

```python
# plugins/my_plugin/main.py

_connect_count = 0

# 🏗️ Called once when the app builds plugin tabs
def on_build_tab(ctx, payload):
    ctx.register_tab(
        title="📊 My Stats",
        icon="📊",
        html="<h2>Plugin Loaded</h2><p>Waiting for events...</p>"
    )
    ctx.log("Tab registered successfully")

# 🔌 Called when VPN connects
def on_connect(ctx, payload):
    global _connect_count
    _connect_count += 1
    ctx.log(f"Connection #{_connect_count} established")
    
    # Update tab content dynamically (same title = replaces content)
    ctx.register_tab(
        title="📊 My Stats",
        icon="📊",
        html=f"""
        <h2> Active Connection</h2>
        <p>Total connections this session: <b>{_connect_count}</b></p>
        <table>
          <tr><td>Status</td><td><span style='color:#2E7D32'>Online</span></td></tr>
          <tr><td>Protocol</td><td>{payload.get('config', {}).get('type', 'N/A')}</td></tr>
        </table>
        """
    )

# 🔌 Called when VPN disconnects
def on_disconnect(ctx, payload):
    ctx.register_tab(
        title="📊 My Stats",
        icon="📊",
        html="<h2>🔴 Disconnected</h2><p>Session ended.</p>"
    )

# 📜 Called for every app log line
def on_log(ctx, payload):
    line = payload.get('line', '')
    if "handshake" in line.lower():
        ctx.log("Handshake detected!")

# 📡 Called when ping results arrive
def on_ping_result(ctx, payload):
    host = payload.get('name', '?')
    ms = payload.get('ms', -1)
    if ms > 200:
        ctx.notify(f"⚠️ High latency on {host}: {ms}ms")
```

---

## 🖼️ Creating Custom Tabs & UI

### How it works
1. Request `"ui:tab"` in `plugin.json`.
2. Implement `def on_build_tab(ctx, payload):` in `main.py`.
3. Use `ctx.register_tab(title, icon, html)` to inject content.
4. Call `ctx.register_tab()` again with the **same title** to update the tab dynamically. The host will replace the old content without creating duplicate tabs.

### HTML & CSS Limits
Tabs are rendered using Qt's `QTextBrowser`. It supports a **subset of HTML5/CSS3**:
✅ Works: `<div>`, `<table>`, `<span>`, inline `style="..."`, basic flex-like layouts, emojis, fonts.  
❌ Blocked: `<script>`, `javascript:`, `onload/onerror`, `<iframe>`, `@import`, `url()` in CSS.  
🛡️ All HTML/CSS is sanitized before rendering to prevent XSS or UI breakage.

### ⚠️ Known UI Limitations (Beta)
* **Rendering Bugs:** Qt's HTML engine is not a full web browser. Complex CSS (grid, advanced animations, custom scrollbars) may glitch or fall back to defaults.
* **Performance:** Heavy HTML updates triggered too frequently (e.g., on every ping) may cause minor UI stutter. Use throttling if possible.
* **Global Styles:** `"ui:style"` permission allows patching app-wide CSS, but priority conflicts can occur. **Recommendation:** Prefer inline styles inside `ctx.register_tab()` for stable results.

---

## 🛠 Plugin API (`ctx` Object)

| Method | Description | Example |
| :--- | :--- | :--- |
| `ctx.log(msg)` | Writes to the app log with `[plugin_id]` prefix | `ctx.log("Ready")` |
| `ctx.notify(msg)` | Shows a popup notification (requires `notify:ui`) | `ctx.notify("Done!")` |
| `ctx.register_tab(title, icon, html)` | Creates/updates a sidebar tab | `ctx.register_tab("Stats", "📊", "<p>Hi</p>")` |
| `ctx.set_style(css)` | Patches global app stylesheet (requires `ui:style`) | `ctx.set_style("#sidebar { background: #111; }")` |
| `ctx.clear_style()` | Removes your global CSS patch | `ctx.clear_style()` |

---

## 📦 How to Install?

1. Pack the plugin folder into a **ZIP archive** (root must contain `plugin.json` and `main.py`).
2. In the app, go to **Plugins** → click **+** → **📁 Import from ZIP**.
3. Select the file. The app will validate security, extract it, and launch the sandbox.

---
*Developed for Twi2wi_Re. Unauthorized access to the system through plugins is technically impossible.*  
*UI features are in Beta. Report rendering issues or API bugs via GitHub Issues.* 💖
