from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VERSIONED_CUSTOM_SKILLS_FILE = (
    PROJECT_ROOT / "resources" / "versioned_custom_skills.json"
)
VERSIONED_CUSTOM_SKILLS_SCHEMA = 1
CUSTOM_SKILL_CONDITIONS_KEY = "__custom_skill_conditions__"


def _catalog_path(path: Path | None = None) -> Path:
    return Path(path) if path is not None else VERSIONED_CUSTOM_SKILLS_FILE


def _empty_catalog() -> dict[str, Any]:
    return {"schema_version": VERSIONED_CUSTOM_SKILLS_SCHEMA, "features": {}}


def load_versioned_custom_skill_catalog(path: Path | None = None) -> dict[str, Any]:
    """Load the tracked custom-skill catalog without reading local GUI settings."""
    catalog_path = _catalog_path(path)
    if not catalog_path.exists():
        return _empty_catalog()
    try:
        raw = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取版本化自定义技能文件：{catalog_path}\n{exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("版本化自定义技能文件的根节点必须是 JSON 对象。")
    schema = raw.get("schema_version")
    if schema != VERSIONED_CUSTOM_SKILLS_SCHEMA:
        raise ValueError(
            f"不支持的版本化自定义技能格式：{schema!r}，"
            f"当前只支持版本 {VERSIONED_CUSTOM_SKILLS_SCHEMA}。"
        )
    features = raw.get("features")
    if not isinstance(features, dict):
        raise ValueError("版本化自定义技能文件中的 features 必须是 JSON 对象。")
    return {"schema_version": schema, "features": copy.deepcopy(features)}


def load_versioned_feature_configuration(
    feature_id: str, path: Path | None = None
) -> dict[str, Any]:
    """Convert one feature's release catalog rows into the GUI configuration shape."""
    rows = load_versioned_custom_skill_catalog(path)["features"].get(feature_id, [])
    if rows in (None, []):
        return {}
    if not isinstance(rows, list):
        raise ValueError(f"{feature_id} 的版本化自定义技能必须是 JSON 数组。")

    configuration: dict[str, Any] = {CUSTOM_SKILL_CONDITIONS_KEY: {}}
    seen_rows: set[tuple[str, str]] = set()
    for index, raw_row in enumerate(rows, start=1):
        if not isinstance(raw_row, dict):
            raise ValueError(f"{feature_id} 的第 {index} 项自定义技能必须是 JSON 对象。")
        group = str(raw_row.get("modification_type") or "").strip()
        skill = str(raw_row.get("skill") or "").strip()
        condition = str(raw_row.get("condition") or "").strip()
        raw_value = raw_row.get("value")
        value = str(raw_value if raw_value is not None else "").strip()
        if not group or not skill or not condition or not value:
            raise ValueError(
                f"{feature_id} 的第 {index} 项缺少 modification_type、skill、condition 或 value。"
            )
        row_key = (group, skill)
        if row_key in seen_rows:
            raise ValueError(
                f"{feature_id} 中存在重复的版本化技能：{group} / {skill}。"
            )
        seen_rows.add(row_key)
        previous_condition = configuration[CUSTOM_SKILL_CONDITIONS_KEY].get(skill)
        if previous_condition is not None and previous_condition != condition:
            raise ValueError(f"{feature_id} 中同一技能“{skill}”使用了不同查询条件。")
        configuration[CUSTOM_SKILL_CONDITIONS_KEY][skill] = condition
        configuration.setdefault(group, {})[skill] = {
            "enabled": bool(raw_row.get("enabled", True)),
            "value": value,
        }
    return configuration


def merge_versioned_feature_configuration(
    feature_id: str, local_configuration: Any = None, path: Path | None = None
) -> dict[str, Any]:
    """Use the release catalog as defaults and local settings as user overrides."""
    merged = load_versioned_feature_configuration(feature_id, path)
    local = local_configuration if isinstance(local_configuration, dict) else {}
    for key, value in local.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(copy.deepcopy(value))
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def custom_skill_rows_from_configuration(
    configuration: Any, group_names: Iterable[str]
) -> list[dict[str, Any]]:
    """Extract only GUI-defined skills into a stable, reviewable release format."""
    source = configuration if isinstance(configuration, dict) else {}
    conditions = source.get(CUSTOM_SKILL_CONDITIONS_KEY, {})
    if not isinstance(conditions, dict):
        conditions = {}
    rows: list[dict[str, Any]] = []
    for group_name in group_names:
        group = source.get(group_name, {})
        if not isinstance(group, dict):
            continue
        for raw_skill, raw_item in group.items():
            skill = str(raw_skill or "").strip()
            condition = str(conditions.get(skill) or "").strip()
            if not skill or not condition:
                continue
            item = raw_item if isinstance(raw_item, dict) else {"value": raw_item}
            rows.append(
                {
                    "modification_type": group_name,
                    "skill": skill,
                    "condition": condition,
                    "enabled": bool(item.get("enabled", True)),
                    "value": str(
                        item.get("value") if item.get("value") is not None else ""
                    ),
                }
            )
    return rows


def save_versioned_feature_configuration(
    feature_id: str,
    configuration: Any,
    group_names: Iterable[str],
    path: Path | None = None,
) -> tuple[Path, int]:
    """Replace one feature's tracked custom skills while preserving other features."""
    catalog_path = _catalog_path(path)
    catalog = load_versioned_custom_skill_catalog(catalog_path)
    features = catalog["features"]
    rows = custom_skill_rows_from_configuration(configuration, group_names)
    if rows:
        features[feature_id] = rows
    else:
        features.pop(feature_id, None)
    catalog["features"] = {key: features[key] for key in sorted(features)}

    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = catalog_path.with_name(f".{catalog_path.name}.tmp")
    try:
        temporary.write_text(
            json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(catalog_path)
    finally:
        temporary.unlink(missing_ok=True)
    return catalog_path, len(rows)


def versioned_custom_skill_count(feature_id: str, path: Path | None = None) -> int:
    rows = load_versioned_custom_skill_catalog(path)["features"].get(feature_id, [])
    return len(rows) if isinstance(rows, list) else 0
