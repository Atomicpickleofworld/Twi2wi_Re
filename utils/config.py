import sys
import os
import logging
from pathlib import Path

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.getenv("APPDATA")) / "Twi2wi"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONF_DIR = DATA_DIR / "conf"
CONF_DIR.mkdir(exist_ok=True)

CONFIGS_FILE = DATA_DIR / "configs.json"
ACTIVE_CONFIG_JSON = CONF_DIR / "active_config.json"
ACTIVE_CONFIG_CONF = CONF_DIR / "active_config.conf"
SINGBOX_PATH = BASE_DIR / "sing-box.exe"
AMNEZIAWG_PATH = BASE_DIR / "amneziawg.exe"

logging.basicConfig(
    filename=str(BASE_DIR / "vpn_debug.log"),
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s"
)