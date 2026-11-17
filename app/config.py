import os
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / '.env'
DB_FILE = ROOT / 'data' / 'xhotlab.sqlite3'


def scan_minutes() -> int:
    values = dotenv_values(ENV_FILE) if ENV_FILE.exists() else {}
    minutes = int(os.environ.get('SCAN_INTERVAL_MINUTES') or values.get('SCAN_INTERVAL_MINUTES') or 15)
    if minutes < 5:
        raise ValueError('扫描间隔最少为 5 分钟')
    return minutes
