from __future__ import annotations

import hashlib
import importlib
import json
import os
import struct
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from .config import DatabaseProfile, PROJECT_ROOT
from .features import CUSTOM_SKILL_CONDITIONS_KEY, Feature

ICON_CACHE_ROOT = PROJECT_ROOT / ".db_tool_cache" / "spell_icons"
ICON_CACHE_SIZE = 48
_CACHE_LOCK = threading.RLock()


@dataclass(frozen=True)
class SkillIconReference:
    spell_id: int
    spell_icon_id: int
    active_icon_id: int = 0

    @property
    def effective_icon_id(self) -> int:
        return self.spell_icon_id or self.active_icon_id


@dataclass(frozen=True)
class SpellIconSyncResult:
    paths: dict[str, Path]
    changed_skills: frozenset[str] = frozenset()
    error: str = ""


def load_spell_icon_dbc(dbc_file: str | Path) -> dict[int, str]:
    """Read a WoW 3.3.5a SpellIcon.dbc into an O(1) icon path lookup."""
    path = Path(dbc_file).expanduser()
    data = path.read_bytes()
    if len(data) < 20:
        raise ValueError(f"DBC 文件太小：{path}")
    magic, record_count, field_count, record_size, string_block_size = (
        struct.unpack_from("<4s4I", data, 0)
    )
    if magic != b"WDBC":
        raise ValueError(f"不是标准 WDBC 文件：{path}")
    if field_count != 2 or record_size != 8:
        raise ValueError(
            "SpellIcon.dbc 结构不匹配："
            f"field_count={field_count}, record_size={record_size}"
        )
    records_offset = 20
    strings_offset = records_offset + record_count * record_size
    strings_end = strings_offset + string_block_size
    if strings_end > len(data):
        raise ValueError(f"SpellIcon.dbc 文件不完整：{path}")
    string_block = data[strings_offset:strings_end]
    icon_map: dict[int, str] = {}
    for index in range(record_count):
        icon_id, name_offset = struct.unpack_from(
            "<II", data, records_offset + index * record_size
        )
        if not name_offset or name_offset >= len(string_block):
            continue
        string_end = string_block.find(b"\0", name_offset)
        if string_end < 0:
            continue
        name = string_block[name_offset:string_end].decode("utf-8", errors="replace")
        if name:
            icon_map[int(icon_id)] = name
    return icon_map


def get_spell_icon_path(
    spell_icon_id: int,
    icon_map: dict[int, str],
    extracted_client_root: str | Path,
) -> Path | None:
    """Resolve the direct extracted-client BLP path described in the project doc."""
    icon_name = icon_map.get(int(spell_icon_id))
    if not icon_name:
        return None
    relative = icon_name.replace("\\", "/").lstrip("/") + ".blp"
    return Path(extracted_client_root).expanduser() / relative


def _file_signature(path: Path) -> str:
    stat = path.stat()
    return f"{stat.st_size}:{stat.st_mtime_ns}"


def spell_icon_resource_directories(
    extracted_client_root: str | Path,
) -> tuple[Path, ...]:
    """Return supported BLP directories in deterministic lookup order."""
    root = Path(extracted_client_root).expanduser()
    candidates = (
        root / "Interface" / "Icons",
        root / "Interface" / "Spellbook",
        root / "interface" / "icons",
        root / "interface" / "spellbook",
        root / "Icons",
        root / "Spellbook",
        root,
    )
    directories: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        identity = str(candidate.absolute())
        if identity in seen or not candidate.is_dir():
            continue
        if candidate == root and candidate.name.lower() not in {"icons", "spellbook"}:
            try:
                if not any(
                    path.is_file() and path.suffix.lower() == ".blp"
                    for path in candidate.iterdir()
                ):
                    continue
            except OSError:
                continue
        seen.add(identity)
        directories.append(candidate)
    return tuple(directories)


def _condition_map(feature: Feature, configuration: Any) -> dict[str, str]:
    normalized = feature.normalize_configuration(configuration)
    module = importlib.import_module(feature.module)
    conditions = dict(module.cond)
    custom = normalized.get(CUSTOM_SKILL_CONDITIONS_KEY, {})
    if isinstance(custom, dict):
        conditions.update(custom)
    names = dict.fromkeys(
        skill
        for group in feature.config_groups
        for skill in normalized[group.config_name]
    )
    return {name: str(conditions.get(name, "")) for name in names}


def _cache_key(
    profile: DatabaseProfile, feature: Feature, skill: str, condition: str
) -> str:
    identity = json.dumps(
        [profile.target_label, feature.id, skill, condition],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


class SpellIconCache:
    """Persistent PNG cache backed by SpellIcon.dbc and extracted BLP resources."""

    def __init__(
        self,
        dbc_file: str | Path = "",
        extracted_client_root: str | Path = "",
        cache_root: str | Path = ICON_CACHE_ROOT,
    ):
        self.dbc_file = Path(dbc_file).expanduser() if str(dbc_file).strip() else None
        self.client_root = (
            Path(extracted_client_root).expanduser()
            if str(extracted_client_root).strip()
            else None
        )
        self.cache_root = Path(cache_root)
        self.index_file = self.cache_root / "index.json"
        # All cache instances share the same index file. A process-wide lock
        # prevents an older background worker from racing a newly configured
        # cache instance and overwriting its index update.
        self._lock = _CACHE_LOCK
        self._index: dict[str, Any] | None = None
        self._dbc_signature = ""
        self._icon_map: dict[int, str] = {}
        self._blp_index: dict[str, Path] | None = None

    @property
    def configured(self) -> bool:
        return bool(
            self.dbc_file
            and self.dbc_file.is_file()
            and self.client_root
            and self.client_root.is_dir()
        )

    def _load_index(self) -> dict[str, Any]:
        if self._index is not None:
            return self._index
        try:
            raw = json.loads(self.index_file.read_text(encoding="utf-8"))
            entries = raw.get("entries", {}) if isinstance(raw, dict) else {}
            if not isinstance(entries, dict):
                entries = {}
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            entries = {}
        self._index = {"version": 1, "entries": entries}
        return self._index

    def _save_index(self) -> None:
        self.cache_root.mkdir(parents=True, exist_ok=True)
        temporary = self.index_file.with_name(f".{self.index_file.name}.tmp")
        payload = json.dumps(self._load_index(), ensure_ascii=False, indent=2)
        try:
            temporary.write_text(payload, encoding="utf-8")
            temporary.replace(self.index_file)
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def _conditions_and_keys(
        self, profile: DatabaseProfile, feature: Feature, configuration: Any
    ) -> tuple[dict[str, str], dict[str, str]]:
        conditions = _condition_map(feature, configuration)
        return conditions, {
            skill: _cache_key(profile, feature, skill, condition)
            for skill, condition in conditions.items()
        }

    def cached_paths(
        self, profile: DatabaseProfile, feature: Feature, configuration: Any
    ) -> dict[str, Path]:
        """Return existing PNGs without touching the DB or source resources."""
        with self._lock:
            _, keys = self._conditions_and_keys(profile, feature, configuration)
            entries = self._load_index()["entries"]
            result: dict[str, Path] = {}
            for skill, key in keys.items():
                entry = entries.get(key, {})
                filename = entry.get("png") if isinstance(entry, dict) else None
                if not filename:
                    continue
                path = self.cache_root / str(filename)
                if path.is_file():
                    result[skill] = path
            return result

    def _load_icon_map(self) -> dict[int, str]:
        if not self.dbc_file or not self.dbc_file.is_file():
            raise FileNotFoundError("请先配置 SpellIcon.dbc 文件")
        signature = _file_signature(self.dbc_file)
        if signature != self._dbc_signature:
            self._icon_map = load_spell_icon_dbc(self.dbc_file)
            self._dbc_signature = signature
        return self._icon_map

    def _resource_directories(self) -> tuple[Path, ...]:
        if not self.client_root:
            return ()
        return spell_icon_resource_directories(self.client_root)

    def _resolve_source(self, icon_id: int, icon_map: dict[int, str]) -> tuple[str, Path | None]:
        icon_name = icon_map.get(int(icon_id), "")
        if not icon_name or not self.client_root:
            return icon_name, None
        direct = get_spell_icon_path(icon_id, icon_map, self.client_root)
        if direct and direct.is_file():
            return icon_name, direct
        resource_directories = self._resource_directories()
        if not resource_directories:
            return icon_name, None
        if self._blp_index is None:
            self._blp_index = {}
            for directory in resource_directories:
                for path in directory.iterdir():
                    if path.is_file() and path.suffix.lower() == ".blp":
                        # Icons takes precedence over Spellbook if a client dump
                        # happens to contain the same basename in both folders.
                        self._blp_index.setdefault(path.name.lower(), path)
        filename = Path(icon_name.replace("\\", "/")).name + ".blp"
        return icon_name, self._blp_index.get(filename.lower())

    @staticmethod
    def _convert_blp(source: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.tmp")
        try:
            with Image.open(source) as image:
                image.seek(0)
                converted = image.convert("RGBA")
                converted.thumbnail((ICON_CACHE_SIZE, ICON_CACHE_SIZE), Image.Resampling.LANCZOS)
                converted.save(temporary, format="PNG")
            temporary.replace(target)
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def sync(
        self,
        profile: DatabaseProfile,
        feature: Feature,
        configuration: Any,
        references: dict[str, SkillIconReference],
    ) -> SpellIconSyncResult:
        """Compare DB/resource metadata with cache and regenerate only changed icons."""
        with self._lock:
            # A different cache instance may have updated index.json while this
            # instance was idle. Reload it before every background reconciliation.
            self._index = None
            self._blp_index = None
            cached = self.cached_paths(profile, feature, configuration)
            if not self.configured:
                return SpellIconSyncResult(
                    cached,
                    error=(
                        "未配置 SpellIcon.dbc 或已解压的 "
                        "Interface/Icons、Interface/Spellbook 目录"
                    ),
                )
            try:
                icon_map = self._load_icon_map()
            except Exception as exc:
                return SpellIconSyncResult(cached, error=str(exc))

            _, keys = self._conditions_and_keys(profile, feature, configuration)
            entries = self._load_index()["entries"]
            paths = dict(cached)
            changed: set[str] = set()
            errors: list[str] = []
            dirty = False

            for skill, key in keys.items():
                reference = references.get(skill)
                icon_id = int(reference.effective_icon_id or 0) if reference else 0
                old = entries.get(key, {}) if isinstance(entries.get(key), dict) else {}
                if reference is None or icon_id <= 0:
                    if old:
                        old_filename = old.get("png")
                        entries.pop(key, None)
                        paths.pop(skill, None)
                        if old_filename:
                            try:
                                (self.cache_root / str(old_filename)).unlink(missing_ok=True)
                            except OSError:
                                pass
                        changed.add(skill)
                        dirty = True
                    continue
                icon_name, source = self._resolve_source(icon_id, icon_map)
                if source is None:
                    errors.append(f"{skill} 的图标资源不存在")
                    if old:
                        old_filename = old.get("png")
                        entries.pop(key, None)
                        paths.pop(skill, None)
                        if old_filename:
                            try:
                                (self.cache_root / str(old_filename)).unlink(missing_ok=True)
                            except OSError:
                                pass
                        changed.add(skill)
                        dirty = True
                    continue
                source_signature = _file_signature(source)
                filename = f"{key[:24]}-{icon_id}.png"
                target = self.cache_root / filename
                try:
                    target_signature = _file_signature(target) if target.is_file() else ""
                except OSError:
                    target_signature = ""
                same = (
                    old.get("spell_id") == int(reference.spell_id)
                    and old.get("icon_id") == icon_id
                    and old.get("icon_name") == icon_name
                    and old.get("source") == str(source)
                    and old.get("source_signature") == source_signature
                    and old.get("dbc_signature") == self._dbc_signature
                    and old.get("png") == filename
                    and old.get("png_signature") == target_signature
                    and bool(target_signature)
                )
                if same:
                    paths[skill] = target
                    continue
                try:
                    self._convert_blp(source, target)
                except Exception as exc:
                    errors.append(f"{skill} 图标解码失败：{exc}")
                    continue
                old_filename = old.get("png")
                entries[key] = {
                    "profile": profile.target_label,
                    "feature_id": feature.id,
                    "skill": skill,
                    "spell_id": int(reference.spell_id),
                    "icon_id": icon_id,
                    "active_icon_id": int(reference.active_icon_id or 0),
                    "icon_name": icon_name,
                    "source": str(source),
                    "source_signature": source_signature,
                    "dbc_signature": self._dbc_signature,
                    "png": filename,
                    "png_signature": _file_signature(target),
                }
                if old_filename and old_filename != filename:
                    try:
                        (self.cache_root / str(old_filename)).unlink(missing_ok=True)
                    except OSError:
                        pass
                paths[skill] = target
                changed.add(skill)
                dirty = True

            if dirty:
                self._save_index()
            error = "；".join(dict.fromkeys(errors[:3]))
            if len(errors) > 3:
                error += f"；另有 {len(errors) - 3} 项"
            return SpellIconSyncResult(paths, frozenset(changed), error)


def suggested_spell_icon_paths() -> tuple[str, str]:
    """Return optional defaults from environment or supported project layouts."""
    dbc = os.environ.get("WOW_SPELL_ICON_DBC", "").strip()
    root = os.environ.get("WOW_EXTRACTED_CLIENT_ROOT", "").strip()

    bundled_root = PROJECT_ROOT / "assets"
    legacy_root = PROJECT_ROOT / "resources" / "wow_client"
    if not dbc:
        for candidate in (
            bundled_root / "wow_335" / "DBC_335_wotlk" / "SpellIcon.dbc",
            legacy_root / "DBFilesClient" / "SpellIcon.dbc",
        ):
            if candidate.is_file():
                dbc = str(candidate)
                break
    if not root:
        for candidate in (bundled_root, legacy_root):
            if spell_icon_resource_directories(candidate):
                root = str(candidate)
                break
    return dbc, root
