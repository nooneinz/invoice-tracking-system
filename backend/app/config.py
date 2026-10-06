import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

_env_file = BASE_DIR / ".env"
if _env_file.exists():
    for line in _env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'invoices.db'}")
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-env")
JWT_HOURS = int(os.getenv("JWT_HOURS", "12"))
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "claude-sonnet-5-5")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@company.local")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
ADMIN_NAME = os.getenv("ADMIN_NAME", "مشرف النظام")
DISABLE_SCHEDULER = os.getenv("DISABLE_SCHEDULER", "") == "1"

# إرسال البريد الفعلي: بدون SMTP_HOST تبقى الرسائل في صندوق الصادر ولا تُرسل
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "")

# توقيع webhook بوابة الدفع (HMAC-SHA256 على جسم الطلب)
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

# سلطنة عُمان: UTC+4
TZ_OFFSET_HOURS = 4
