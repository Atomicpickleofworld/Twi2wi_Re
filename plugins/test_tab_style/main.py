# plugins/test_tab_style/main.py
"""
Plugin Development Tutorial — встроенный гайд по созданию плагинов.
Показывает все возможности Plugin API: хуки, вкладки, уведомления, логи.
"""

_connect_count = 0
_last_ping_data = {}
_current_section = "intro"  # intro | structure | hooks | tabs | security


def on_build_tab(ctx, payload):
    """Создаёт вкладку-туториал при загрузке плагина."""
    ctx.register_tab(
        title="🧩 Гайд",
        icon="📖",
        html=_render_tutorial()
    )
    ctx.log("[Tutorial] Вкладка создана")


def on_connect(ctx, payload):
    """Демонстрирует обновление вкладки при событиях."""
    global _connect_count
    _connect_count += 1
    ctx.register_tab(
        title="🧩 Гайд",
        icon="📖",
        html=_render_tutorial()
    )
    ctx.notify(f"✅ Подключение #{_connect_count} — вкладка обновлена!")


def on_disconnect(ctx, payload):
    """Показывает, что вкладка может реагировать на отключение."""
    ctx.register_tab(
        title="🧩 Гайд",
        icon="📖",
        html=_render_tutorial()
    )


def on_ping_result(ctx, payload):
    """Сохраняет данные пинга для отображения в туториале."""
    name = payload.get("name", "?")
    ms = payload.get("ms", -1)
    _last_ping_data[name] = ms


# ═══════════════════════════════════════════════════════════════════════
# HTML-рендеринг туториала
# ═══════════════════════════════════════════════════════════════════════

def _render_tutorial() -> str:
    ping_rows = ""
    for host, ms in list(_last_ping_data.items())[-5:]:
        if ms == -1:
            badge = "<span class='bad'>TIMEOUT</span>"
        elif ms < 100:
            badge = f"<span class='good'>{ms} ms</span>"
        elif ms <= 200:
            badge = f"<span class='warn'>{ms} ms</span>"
        else:
            badge = f"<span class='bad'>{ms} ms</span>"
        ping_rows += f"<tr><td>{host}</td><td>{badge}</td></tr>"

    if not ping_rows:
        ping_rows = "<tr><td colspan='2' style='color:#9B8AAE;'>Ожидание данных пинга...</td></tr>"

    return f"""
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', 'Consolas', sans-serif;
            font-size: 13px;
            color: #2C2430;
            line-height: 1.6;
            padding: 8px;
        }}
        h1 {{
            color: #7A5C9A;
            font-size: 22px;
            font-weight: 700;
            margin-bottom: 6px;
            border-bottom: 2px solid #E8DFF0;
            padding-bottom: 8px;
        }}
        h2 {{
            color: #7A5C9A;
            font-size: 16px;
            font-weight: 600;
            margin: 18px 0 8px 0;
        }}
        h3 {{
            color: #9B8AAE;
            font-size: 13px;
            font-weight: 600;
            margin: 12px 0 4px 0;
        }}
        p {{ margin: 6px 0; }}
        code {{
            background: #F0EAF8;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 12px;
            color: #6B3FA0;
        }}
        pre {{
            background: #F8F6F2;
            border: 1px solid #E8DFF0;
            border-radius: 8px;
            padding: 12px;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 11px;
            line-height: 1.5;
            color: #4A3B52;
            overflow-x: auto;
            margin: 8px 0;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 8px 0;
        }}
        td, th {{
            border: 1px solid #E8DFF0;
            padding: 8px 12px;
            text-align: left;
            font-size: 12px;
        }}
        th {{
            background: #EDE5F5;
            color: #7A5C9A;
            font-size: 10px;
            letter-spacing: 1px;
            text-transform: uppercase;
        }}
        .card {{
            background: #FFFFFF;
            border: 1px solid #E8DFF0;
            border-radius: 10px;
            padding: 14px;
            margin: 10px 0;
        }}
        .badge {{
            display: inline-block;
            background: #E6D8FF;
            color: #7A5C9A;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: bold;
            letter-spacing: 1px;
        }}
        .good {{ color: #2E7D32; font-weight: bold; }}
        .bad  {{ color: #C62828; font-weight: bold; }}
        .warn {{ color: #F57C00; font-weight: bold; }}
        .note {{
            background: #FFF9E6;
            border-left: 3px solid #FFC107;
            padding: 8px 12px;
            margin: 10px 0;
            font-size: 11px;
            color: #6B5A00;
            border-radius: 0 6px 6px 0;
        }}
        .info {{
            background: #E8F4FD;
            border-left: 3px solid #2196F3;
            padding: 8px 12px;
            margin: 10px 0;
            font-size: 11px;
            color: #0D47A1;
            border-radius: 0 6px 6px 0;
        }}
        .live-data {{
            background: #F0FAF0;
            border: 1px solid #C8E6C9;
            border-radius: 8px;
            padding: 10px;
            margin: 10px 0;
        }}
        .footer {{
            text-align: center;
            color: #9B8AAE;
            font-size: 10px;
            margin-top: 24px;
            border-top: 1px solid #E8DFF0;
            padding-top: 12px;
        }}
    </style>

    <h1>🧩 Plugin Development Guide</h1>
    <p>Добро пожаловать в туториал по созданию плагинов для <b>Twi2wi_Re</b>.</p>
    <p>Эта вкладка — живой пример плагина. Она создана через <code>ctx.register_tab()</code> и обновляется при событиях VPN.</p>

    <!-- ═══ ЖИВЫЕ ДАННЫЕ ═══ -->
    <div class="live-data">
        <h3 style="margin-top:0;">📡 Live Plugin Data</h3>
        <table>
            <tr><td>Подключений за сессию</td><td><b class="good">{_connect_count}</b></td></tr>
            <tr><td>Плагин активен</td><td><span class="good">✅ Да</span></td></tr>
        </table>
        <h3>🏓 Последние пинги</h3>
        <table>
            <tr><th>Хост</th><th>Пинг</th></tr>
            {ping_rows}
        </table>
    </div>

    <!-- ═══ БЫСТРЫЙ СТАРТ ═══ -->
    <h2>🚀 Быстрый старт</h2>
    <div class="card">
        <p>Минимальный плагин состоит из двух файлов:</p>
        <pre>plugins/my_plugin/
├── <b>plugin.json</b>   ← манифест
└── <b>main.py</b>       ← код</pre>
    </div>

    <!-- ═══ plugin.json ═══ -->
    <h2>📋 Манифест (plugin.json)</h2>
    <div class="card">
        <pre>{{
  "id": "my_plugin_id",
  "name": "My Plugin",
  "version": "1.0.0",
  "entry": "main.py",
  "description": "Описание плагина",
  "permissions": [
    "hooks:read",
    "notify:ui",
    "ui:tab"
  ]
}}</pre>
        <table>
            <tr><th>Поле</th><th>Описание</th></tr>
            <tr><td><code>id</code></td><td>Уникальный ID (латиница + подчёркивания)</td></tr>
            <tr><td><code>entry</code></td><td>Точка входа (имя .py файла)</td></tr>
            <tr><td><code>permissions</code></td><td>Список прав (см. ниже)</td></tr>
        </table>
    </div>

    <!-- ═══ ПРАВА ═══ -->
    <h2>🔐 Права (Permissions)</h2>
    <table>
        <tr><th>Право</th><th>Что даёт</th></tr>
        <tr><td><code>hooks:read</code></td><td><b>Обязательно.</b> Получать события от приложения.</td></tr>
        <tr><td><code>notify:ui</code></td><td>Показывать всплывающие уведомления.</td></tr>
        <tr><td><code>ui:tab</code></td><td>Создавать вкладку в сайдбаре.</td></tr>
        <tr><td><code>ui:style</code></td><td>Патчить глобальные стили <span class="warn">(Beta, нестабильно)</span>.</td></tr>
    </table>

    <!-- ═══ ХУКИ ═══ -->
    <h2>🪝 Хуки (События)</h2>
    <p>Плагин реализует функции с именами хуков. Они вызываются автоматически.</p>
    <table>
        <tr><th>Хук</th><th>Когда вызывается</th><th>payload</th></tr>
        <tr><td><code>on_build_tab</code></td><td>При загрузке плагина</td><td><code>{{}}</code></td></tr>
        <tr><td><code>on_connect</code></td><td>VPN подключился</td><td><code>{{"config": {{...}}}}</code></td></tr>
        <tr><td><code>on_disconnect</code></td><td>VPN отключился</td><td><code>{{}}</code></td></tr>
        <tr><td><code>on_log</code></td><td>Новая строка лога</td><td><code>{{"line": "..."}}</code></td></tr>
        <tr><td><code>on_ping_result</code></td><td>Результат пинга</td><td><code>{{"name":"...","ms":42,"loss":0.0}}</code></td></tr>
    </table>

    <div class="note">
        <b>💡 Совет:</b> Используйте <code>on_build_tab</code> для создания вкладки, а <code>on_connect</code> — для обновления данных.
    </div>

    <!-- ═══ API ═══ -->
    <h2>🛠 Plugin API (ctx)</h2>
    <p>Все методы доступны через объект <code>ctx</code>, передаваемый в каждый хук:</p>
    <table>
        <tr><th>Метод</th><th>Описание</th></tr>
        <tr><td><code>ctx.log(msg)</code></td><td>Запись в лог приложения</td></tr>
        <tr><td><code>ctx.notify(msg)</code></td><td>Всплывающее уведомление</td></tr>
        <tr><td><code>ctx.register_tab(title, icon, html)</code></td><td>Создать/обновить вкладку</td></tr>
    </table>

    <!-- ═══ ВКЛАДКИ ═══ -->
    <h2>🖼️ Создание вкладок</h2>
    <div class="card">
        <pre>def on_build_tab(ctx, payload):
    ctx.register_tab(
        title="📊 Статистика",
        icon="📊",
        html="&lt;h2&gt;Привет, мир!&lt;/h2&gt;"
    )</pre>
        <p>Вызов <code>register_tab</code> с тем же <b>title</b> обновит содержимое, а не создаст дубликат.</p>
    </div>

    <div class="info">
        <b>📖 HTML поддерживает:</b> таблицы, заголовки, inline-стили, эмодзи, списки.<br>
        <<b>🚫 Заблокировано:</b> JS-скрипты, iframe, внешние ссылки, @import.
    </div>

    <!-- ═══ БЕЗОПАСНОСТЬ ═══ -->
    <h2>🔒 Безопасность</h2>
    <table>
        <tr><th>Ограничение</th><th>Описание</th></tr>
        <tr><td>Изоляция subprocess</td><td>Плагин запущен в отдельном процессе Python</td></tr>
        <tr><td>Заблокированные модули</td><td><code>os, sys, socket, subprocess, requests</code></td></tr>
        <tr><td>Файловая система</td><td>Доступ только к своей папке <code>plugins/&lt;id&gt;/</code></td></tr>
        <tr><td>Сеть</td><td>Запрещена полностью</td></tr>
        <tr><td>HTML-санитайзер</td><td>Удаляет <code>&lt;script&gt;</code>, обработчики событий, внешние ссылки</td></tr>
    </table>

    <!-- ═══ ПРИМЕР ═══ -->
    <h2>📦 Полный пример</h2>
    <div class="card">
        <pre># plugins/my_plugin/main.py
_connections = 0

def on_build_tab(ctx, payload):
    ctx.register_tab(
        title="📊 Статистика",
        icon="📊",
        html="&lt;h2&gt;Ожидание подключения...&lt;/h2&gt;"
    )

def on_connect(ctx, payload):
    global _connections
    _connections += 1
    ctx.register_tab(
        title="📊 Статистика",
        icon="📊",
        html=f"&lt;h2&gt;🟢 Онлайн&lt;/h2&gt;&lt;p&gt;Подключений: {{_connections}}&lt;/p&gt;"
    )
    ctx.notify(f"✅ Подключение #{{_connections}}")

def on_disconnect(ctx, payload):
    ctx.register_tab(
        title="📊 Статистика",
        icon="📊",
        html="&lt;h2&gt;🔴 Оффлайн&lt;/h2&gt;"
    )

def on_ping_result(ctx, payload):
    if payload.get('ms', -1) > 200:
        ctx.log(f"Высокий пинг: {{payload['ms']}}ms")</pre>
    </div>

    <div class="footer">
        Twi2wi_Re Plugin API v1.0 · Beta · <b>test_tab_style</b> v1.0.0<br>
        Эта вкладка — живой плагин. Она обновляется при подключении VPN.
    </div>
    """