import os
import yaml

ROOT_PATH = os.path.dirname(__file__)
CONFIG_FILE_PATH = os.path.join(ROOT_PATH, "env.yaml")

if os.path.exists(CONFIG_FILE_PATH):
    with open(CONFIG_FILE_PATH, "r") as r_file:
        data = yaml.safe_load(r_file)
else:
    data = dict()


class ApplicationConfig:
    DB_URI = data.get("DB_URI", "sqlite+aiosqlite:///./test.db")
    MIGRATION_DB_URI = data.get("MIGRATION_DB_URI", "sqlite:///./test.db")
    REDIS_URL = data.get("REDIS_URL", "redis://localhost:6379/0")
    API_PREFIX = data.get("API_PREFIX", "/api")
    API_PORT = data.get("API_PORT", 8000)
    API_HOST = data.get("API_HOST", "0.0.0.0")
    CORS_ORIGINS = data.get("CORS_ORIGINS", [])
    CORS_ALLOW_CREDENTIALS = data.get("CORS_ALLOW_CREDENTIALS", True)
    LOG_LEVEL = data.get("LOG_LEVEL", "INFO")
    AUTH_DISABLED = bool(data.get("AUTH_DISABLED", False))
    ENABLE_LOGGING_MIDDLEWARE = bool(data.get("ENABLE_LOGGING_MIDDLEWARE", 1))
    ENABLE_SENTRY = data.get("ENABLE_SENTRY", 0)
    DSN_SENTRY = data.get("DSN_SENTRY", "")
    SENTRY_ENVIRONMENT = data.get("SENTRY_ENVIRONMENT", "dev")
    CACHE_BACKEND = data.get("CACHE_BACKEND", "redis")

    # Abnormal Usage Detection Configuration (UC-37)
    ANOMALY_HOURLY_THRESHOLD = data.get("ANOMALY_HOURLY_THRESHOLD", 100.0)  # Credits per hour
    ANOMALY_DAILY_THRESHOLD = data.get("ANOMALY_DAILY_THRESHOLD", 500.0)  # Credits per day
    ANOMALY_DETECTION_ENABLED = bool(data.get("ANOMALY_DETECTION_ENABLED", True))
    ANOMALY_NOTIFICATION_WEBHOOK = data.get("ANOMALY_NOTIFICATION_WEBHOOK", None)

    # Monthly Allocation Configuration (UC-38)
    MONTHLY_ALLOCATION_ENABLED = bool(data.get("MONTHLY_ALLOCATION_ENABLED", True))
    MONTHLY_ALLOCATION_CREDIT_PRICE = data.get("MONTHLY_ALLOCATION_CREDIT_PRICE", 0.015)  # $ per credit
    MONTHLY_ALLOCATION_RUN_DAY = data.get("MONTHLY_ALLOCATION_RUN_DAY", 1)  # Day of month to run

    # Ledger Reconciliation Configuration (UC-40)
    RECONCILIATION_ENABLED = bool(data.get("RECONCILIATION_ENABLED", True))
    RECONCILIATION_INTERVAL_SECONDS = data.get("RECONCILIATION_INTERVAL_SECONDS", 86400)  # Daily
