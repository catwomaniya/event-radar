from pathlib import Path

# Project root (where pyproject.toml lives)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Auth directory for saved browser sessions
AUTH_DIR = PROJECT_ROOT / "auth"
X_BROWSER_STATE_PATH = AUTH_DIR / "x_browser_state.json"
LUMA_BROWSER_STATE_PATH = AUTH_DIR / "luma_browser_state.json"

# Google Sheets service account credentials
DEFAULT_CREDENTIALS_PATH = PROJECT_ROOT / "creds" / "gspread_service_account.json"

# Timing
PAGE_LOAD_TIMEOUT_MS = 15_000
X_DELAY_MIN = 3.0
X_DELAY_MAX = 7.0
SCROLL_PAUSE = 1.5
X_LOGIN_TIMEOUT_MS = 120_000  # 2 minutes for manual login

# Browser
BRAVE_PATH = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# Rate limit backoff
RATE_LIMIT_BACKOFF = [60, 120]  # seconds to wait on rate limit
MAX_RATE_LIMIT_RETRIES = 2
