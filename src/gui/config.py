from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_FILE = PROJECT_ROOT / ".db_tool_gui.json"


@dataclass
class DatabaseProfile:
    name: str = "本地数据库"
    host: str = "localhost"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = "acore_world"
    auth_plugin: str = "mysql_native_password"

    def connector_config(self) -> dict[str, Any]:
        config: dict[str, Any] = {
            "host": self.host.strip(),
            "port": int(self.port),
            "user": self.user.strip(),
            "password": self.password,
            "database": self.database.strip(),
            "connection_timeout": 5,
        }
        if self.auth_plugin.strip():
            config["auth_plugin"] = self.auth_plugin.strip()
        return config

    @property
    def target_label(self) -> str:
        return f"{self.user}@{self.host}:{self.port}/{self.database}"


@dataclass
class AppSettings:
    profiles: list[DatabaseProfile] = field(default_factory=list)
    selected_profile: int = 0
    window_geometry: str = "1280x800"
    feature_configs: dict[str, dict[str, dict[str, dict[str, Any]]]] = field(default_factory=dict)
    dialog_geometries: dict[str, str] = field(default_factory=dict)
    spell_icon_dbc_path: str = ""
    spell_icon_client_root: str = ""


def _default_profiles() -> list[DatabaseProfile]:
    # 与旧版 mysql_core.py 中的目标保持一致，首次启动即可直接选择。
    return [
        DatabaseProfile("远程 AzerothCore", "192.168.71.71", 3306, "root", "root", "acore_world"),
        DatabaseProfile("远程 World", "172.20.1.193", 3306, "root", "ascent", "world"),
        DatabaseProfile("本地 Mangos", "localhost", 3306, "mangos", "mangos", "mangos"),
        DatabaseProfile("本地测试库", "localhost", 3306, "root", "ascent", "vmangos_test_mangos"),
    ]


def load_settings(path: Path = SETTINGS_FILE) -> AppSettings:
    if not path.exists():
        return AppSettings(profiles=_default_profiles())
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        profiles = [DatabaseProfile(**item) for item in raw.get("profiles", [])]
        if not profiles:
            profiles = _default_profiles()
        selected = min(max(int(raw.get("selected_profile", 0)), 0), len(profiles) - 1)
        feature_configs = raw.get("feature_configs", {})
        if not isinstance(feature_configs, dict):
            feature_configs = {}
        dialog_geometries = raw.get("dialog_geometries", {})
        if not isinstance(dialog_geometries, dict):
            dialog_geometries = {}
        dialog_geometries = {
            key: value
            for key, value in dialog_geometries.items()
            if isinstance(key, str) and isinstance(value, str)
        }
        return AppSettings(
            profiles=profiles,
            selected_profile=selected,
            window_geometry=raw.get("window_geometry", "1280x800"),
            dialog_geometries=dialog_geometries,
            feature_configs=feature_configs,
            spell_icon_dbc_path=str(raw.get("spell_icon_dbc_path", "") or ""),
            spell_icon_client_root=str(raw.get("spell_icon_client_root", "") or ""),
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return AppSettings(profiles=_default_profiles())


def save_settings(settings: AppSettings, path: Path = SETTINGS_FILE) -> None:
    """Persist settings atomically so an interrupted write cannot corrupt them."""
    payload = {
        "profiles": [asdict(profile) for profile in settings.profiles],
        "selected_profile": settings.selected_profile,
        "window_geometry": settings.window_geometry,
        "dialog_geometries": settings.dialog_geometries,
        "feature_configs": settings.feature_configs,
        "spell_icon_dbc_path": settings.spell_icon_dbc_path,
        "spell_icon_client_root": settings.spell_icon_client_root,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
    finally:
        # replace() removes the temporary file on success. Clean it up after a
        # failed write/replace as well, without hiding the original exception.
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
