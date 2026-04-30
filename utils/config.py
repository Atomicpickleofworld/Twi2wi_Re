# utils/config.py
import sys
import os
import logging
import json
from pathlib import Path

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

CONF_DIR = BASE_DIR / "configs"
CONF_DIR.mkdir(parents=True, exist_ok=True)

CONFIGS_FILE = BASE_DIR / "configs.json"
ACTIVE_CONFIG_JSON = CONF_DIR / "active_config.json"
ACTIVE_CONFIG_CONF = CONF_DIR / "active_config.conf"
SINGBOX_PATH    = BASE_DIR / "bin" / "sing-box.exe"
AMNEZIAWG_PATH  = BASE_DIR / "bin" / "amneziawg.exe"
if not CONFIGS_FILE.exists():
    CONFIGS_FILE.write_text("[]", encoding="utf-8")


logging.basicConfig(
    filename=str(BASE_DIR / "vpn_debug.log"),
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8"
)