"""Application configuration loaded from environment or local example config."""

import importlib.util
import os
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_local_config(path: Path) -> Optional[ModuleType]:
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location("wangdian_local_config", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@dataclass(frozen=True)
class Settings:
    sid: str
    app_key: str
    app_secret: str
    environment: str
    database_path: Path
    demo_mode: bool

    @property
    def credentials_configured(self) -> bool:
        return bool(self.sid and self.app_key and self.app_secret)


def load_settings() -> Settings:
    local = _load_local_config(PROJECT_ROOT / "examples" / "wangdian_config.py")

    def value(env_name: str, local_name: str, default: str = "") -> str:
        env_value = os.getenv(env_name)
        if env_value is not None:
            return env_value
        return str(getattr(local, local_name, default)) if local else default

    sid = value("WDT_SID", "SID")
    app_key = value("WDT_APP_KEY", "APP_KEY")
    app_secret = value("WDT_APP_SECRET", "APP_SECRET")
    environment = value("WDT_ENV", "ENVIRONMENT", "test")
    configured = bool(sid and app_key and app_secret)
    demo_mode = not configured and os.getenv("WDT_DEMO_DATA", "1") != "0"
    if demo_mode:
        default_name = "inventory_demo.db"
    elif environment.strip().lower() in {"prod", "production", "formal"}:
        default_name = "inventory_production.db"
    else:
        default_name = "inventory.db"
    database_path = Path(
        os.getenv("WDT_DATABASE", str(PROJECT_ROOT / "data" / default_name))
    ).expanduser()
    return Settings(
        sid=sid,
        app_key=app_key,
        app_secret=app_secret,
        environment=environment,
        database_path=database_path,
        demo_mode=demo_mode,
    )
