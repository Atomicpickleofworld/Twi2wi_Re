STYLE = """
QMainWindow, QWidget { background-color: #F8F6F2; color: #2C2430; font-family: 'Segoe UI', 'Consolas', sans-serif; }
#sidebar { background-color: #EDE5F5; border-right: 1px solid #D8C8E8; min-width: 220px; max-width: 220px; }
#logo_label { color: #7A5C9A; font-size: 20px; font-weight: bold; letter-spacing: 3px; padding: 20px 16px 8px 16px; }
QPushButton:focus { outline: none; }
#version_label { color: #9B8AAE; font-size: 10px; padding: 0 16px 20px 16px; letter-spacing: 1px; }
#nav_btn { background: transparent; border: none; color: #6B5A7E; font-size: 12px; letter-spacing: 1px; text-align: left; padding: 12px 20px; border-left: 2px solid transparent; }
#nav_btn:hover { color: #FF9E43; background: rgba(255, 158, 67, 0.08); border-left: 2px solid #FF9E43; }
#nav_btn[active="true"] { color: #FF9E43; background: rgba(255, 158, 67, 0.12); border-left: 2px solid #FF9E43; }
#status_dot_connected { background: #4CAF50; border-radius: 5px; min-width: 10px; max-width: 10px; min-height: 10px; max-height: 10px; }
#status_dot_disconnected { background: #C62828; border-radius: 5px; min-width: 10px; max-width: 10px; min-height: 10px; max-height: 10px; }
#connect_btn { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF9E43, stop:1 #F28C33); border: none; border-radius: 8px; color: #FFFFFF; font-size: 13px; font-weight: bold; letter-spacing: 2px; padding: 10px 14px; margin: 8px 16px; }
#status_dot_waiting { background: #FFC107; border-radius: 5px; min-width: 10px; max-width: 10px; min-height: 10px; max-height: 10px; }
#connect_btn:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FFB74D, stop:1 #FF9E43); }
QListWidget#config_list { background: transparent; border: none; outline: none; }
QListWidget#config_list::item { background: transparent; border-radius: 8px; margin-bottom: 4px; padding: 4px; }
QListWidget#config_list::item:hover { background: rgba(122, 92, 154, 0.08); }
QListWidget#config_list::item:selected { background: #E6D8FF; color: black; }
#card { background: #FDFCF9; border: 1px solid #E8DFF0; border-radius: 12px; padding: 12px; }
#card_title { color: #7A5C9A; font-size: 11px; letter-spacing: 2px; }
#card_host { color: #9B8AAE; font-size: 10px; }
#card_value_good { color: #2E7D32; font-size: 20px; font-weight: bold; }
#card_value_mid   { color: #F57C00; font-size: 20px; font-weight: bold; }
#card_value_bad   { color: #C62828; font-size: 20px; font-weight: bold; }
#card_value_none  { color: #2C2430; font-size: 20px; font-weight: bold; }
#section_title { background-color: rgba(255, 255, 255, 0); color: #7A5C9A; font-size: 11px; letter-spacing: 3px; padding: 0 0 8px 0; }
#add_btn { background: transparent; border: 1px dashed #C8B8D8; border-radius: 8px; color: #7A5C9A; font-size: 12px; padding: 10px; letter-spacing: 1px; }
#add_btn:hover { border-color: #FF9E43; color: #FF9E43; background: rgba(255, 158, 67, 0.05); }
#log_view, #sys_view { background: #FFFFFF; border: 1px solid #E8DFF0; border-radius: 8px; color: #4A3B52; font-family: 'Consolas', monospace; font-size: 11px; padding: 12px; }
QLineEdit { background: #FFFFFF; border: 1px solid #D8C8E8; border-radius: 6px; padding: 8px; color: #2C2430; }
QLineEdit:focus { border-color: #FF9E43; }
QScrollBar:vertical { background: #F8F6F2; width: 6px; border-radius: 3px; }
QScrollBar::handle:vertical { background: #D8C8E8; border-radius: 3px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollArea { background: transparent; border: none; }
#fav_btn { color: #9B8AAE; font-size: 18px; border: none; background: transparent; padding: 0; }
#fav_btn[fav="true"] { color: #FFB74D; }
#menu_btn { color: #7A5C9A; font-size: 16px; border: none; background: transparent; padding: 0; }
#fav_section { background: transparent; border: none; color: #7A5C9A; font-size: 11px; letter-spacing: 3px; padding: 8px 0 4px 0; }
# === ПЛАГИНЫ ===
QFrame#plugin_card {
    background: #FDFCF9;
    border: 1px solid #E8DFF0;
    border-radius: 12px;
    margin-bottom: 0px;
}
QFrame#plugin_card[state="enabled"] {
    background: #FDFCF9;
    border-color: #E8DFF0;
}
QFrame#plugin_card[state="disabled"] {
    background: #EAE5F0;
    border-color: #D0C8DA;
}
QFrame#plugin_card[state="error"] {
    background: #FFF9E6;
    border-color: #FFC107;
}
QFrame#plugin_card:hover {
    border-color: #FF9E43;
}
#status_indicator {
    font-size: 10px;
    font-weight: bold;
    min-width: 80px;
    text-align: center;
    padding: 4px 8px;
    border-radius: 4px;
}
#status_indicator[status="active"] {
    color: #2E7D32;
    background: rgba(76, 175, 80, 0.1);
}
#status_indicator[status="disabled"] {
    color: #C62828;
    background: rgba(155, 45, 48, 0.08);
}
#status_indicator[status="error"] {
    color: #F57C00;
    background: rgba(255, 193, 7, 0.15);
}
"""