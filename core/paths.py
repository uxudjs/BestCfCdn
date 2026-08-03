"""仓库根目录及运行时路径契约。"""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

CONFIG_FILE = PROJECT_ROOT / "config.json"
CONFIG_TEMPLATE_FILE = PROJECT_ROOT / "config" / "config.example.json"
LOCAL_OUTPUT_FILE = PROJECT_ROOT / "ip.local.txt"
REMOTE_OUTPUT_FILE = PROJECT_ROOT / "ip.txt"
TOKEN_FILE = PROJECT_ROOT / "valid_tokens.txt"
IPINFO_CACHE_FILE = PROJECT_ROOT / "ipinfo_cache.txt"
LOG_FILE = PROJECT_ROOT / "cfnb.log"
CRON_LOG_FILE = PROJECT_ROOT / "cron.log"
SCHEDULE_LOCK_FILE = PROJECT_ROOT / ".cfnb_schedule.lock"
SING_BOX_DIR = PROJECT_ROOT / ".sing-box"

_REMOVABLE_CACHE_DIR_NAMES = frozenset(
    {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
)
_PROTECTED_ROOT_NAMES = frozenset(
    {".git", ".venv", ".codegraph", ".sing-box", ".agents"}
)


def is_removable_cache_candidate(path):
    """判断路径是否属于规格允许的可再生缓存白名单。"""
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    try:
        relative = candidate.absolute().relative_to(PROJECT_ROOT)
    except ValueError:
        return False

    if not relative.parts or relative.parts[0] in _PROTECTED_ROOT_NAMES:
        return False
    if relative == Path("ipinfo_cache.txt"):
        return True
    if any(part in _REMOVABLE_CACHE_DIR_NAMES for part in relative.parts):
        return True
    return relative.suffix == ".pyc"
