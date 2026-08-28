from __future__ import annotations

import ast
import importlib
import inspect
import re
import textwrap
from dataclasses import dataclass
from functools import lru_cache
from numbers import Number
from typing import Any

import mysql.connector

from src.customization.base import spell as spell_mod

from .config import DatabaseProfile
from .features import Feature, validate_skill_condition
from .spell_icons import SkillIconReference


@dataclass(frozen=True)
class SkillDetails:
    descriptions: dict[str, str]
    current_values: dict[tuple[str, str], str]
    icons: dict[str, SkillIconReference]


@dataclass(frozen=True)
class SkillConditionPreview:
    count: int
    rows: list[dict[str, Any]]


def skill_names(feature: Feature) -> list[str]:
    """Return configurable skill names once, preserving their source order."""
    return list(
        dict.fromkeys(
            skill
            for group in feature.default_configuration().values()
            for skill in group
        )
    )


def _clean_description(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def _fallback_pattern(skill: str, condition: str) -> str:
    exact = re.search(r"spellname4\s*=\s*'([^']+)'", condition, re.IGNORECASE)
    if exact:
        return exact.group(1)
    like = re.search(r"spellname4\s+like\s*'([^']+)'", condition, re.IGNORECASE)
    if like:
        return like.group(1)
    return re.sub(r"_(?:效果|伤害|几率)$", "", skill)


def _matches_pattern(value: str, pattern: str) -> bool:
    expression = re.escape(pattern).replace("%", ".*").replace("_", ".")
    return re.fullmatch(expression, value or "", re.IGNORECASE) is not None


def _effect_base_values(row: dict[str, Any], effect_type: int) -> list[Number]:
    values: list[Number] = []
    for slot in range(1, 4):
        if row[f"effect_{slot}"] != effect_type:
            continue
        value = row[f"effect_base_points_{slot}"]
        if value is not None and value != -1:
            # The modification SQL treats EffectBasePoints as value - 1.
            values.append(value + 1)
    return values


def _has_trigger_aura(row: dict[str, Any], aura_names: tuple[int, ...]) -> bool:
    return any(
        row[f"effect_{slot}"] == 6
        and row[f"effect_apply_aura_{slot}"] in aura_names
        and (row[f"effect_trigger_spell_{slot}"] or 0) > 0
        for slot in range(1, 4)
    )


@lru_cache(maxsize=None)
def _code_index_labels(method_name: str, variable_name: str) -> dict[int, str]:
    """Read duration/cast-time labels from the dictionaries used by Mod itself."""
    method = getattr(spell_mod.Mod, method_name)
    tree = ast.parse(textwrap.dedent(inspect.getsource(method)))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
            continue
        if not any(isinstance(target, ast.Name) and target.id == variable_name for target in node.targets):
            continue
        labels: dict[int, str] = {}
        # Iterate AST pairs rather than literal_eval(dict), preserving duplicate
        # labels such as the two legacy 5s/2500ms DBC indexes.
        for key_node, value_node in zip(node.value.keys, node.value.values):
            label = ast.literal_eval(key_node)
            index = ast.literal_eval(value_node)
            labels[int(index)] = str(label)
        return labels
    return {}


def _format_number(value: Number) -> str:
    numeric = float(value)
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:g}"


def _format_milliseconds(value: Number) -> str:
    numeric = float(value)
    if numeric < 0:
        return "无限"
    if numeric == 0:
        return "0ms"
    if numeric % 1000 == 0:
        return f"{_format_number(numeric / 1000)}s"
    if numeric >= 1000:
        return f"{_format_number(numeric / 1000)}s"
    return f"{_format_number(numeric)}ms"


def _format_values(values: list[Any], formatter=_format_number) -> str:
    unique = list(dict.fromkeys(value for value in values if value is not None))
    if not unique:
        return ""
    try:
        unique = sorted(unique, key=float)
    except (TypeError, ValueError):
        unique = sorted(unique, key=str)
    rendered = [formatter(value) for value in unique]
    if len(rendered) <= 4:
        return " / ".join(rendered)
    return f"{rendered[0]}–{rendered[-1]}（{len(rendered)}档）"


def _format_index_values(
    values: list[Any], database_labels: dict[int, Number], code_labels: dict[int, str]
) -> str:
    rendered: list[str] = []
    for raw_index in dict.fromkeys(values):
        index = int(raw_index)
        if index in database_labels:
            label = _format_milliseconds(database_labels[index])
        else:
            label = code_labels.get(index, f"索引 {index}")
        if label not in rendered:
            rendered.append(label)
    if not rendered:
        return ""
    if len(rendered) <= 4:
        return " / ".join(rendered)
    return f"{rendered[0]}–{rendered[-1]}（{len(rendered)}档）"


def _lookup_index_values(cursor, table: str, value_column: str, indexes: set[int]) -> dict[int, Number]:
    if not indexes:
        return {}
    placeholders = ", ".join(["%s"] * len(indexes))
    cursor.execute(
        f"SELECT ID AS value_id, {value_column} AS current_value "
        f"FROM {table} WHERE ID IN ({placeholders})",
        tuple(sorted(indexes)),
    )
    return {
        int(row["value_id"]): row["current_value"]
        for row in cursor.fetchall()
        if row["current_value"] is not None
    }


def preview_skill_condition(
    profile: DatabaseProfile, condition: Any, *, limit: int = 20
) -> SkillConditionPreview:
    """Run a read-only preview for a user-defined spell WHERE predicate."""
    predicate = validate_skill_condition(condition)
    safe_limit = max(1, min(int(limit), 100))
    connection = mysql.connector.connect(**profile.connector_config())
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(f"SELECT COUNT(*) AS match_count FROM spell s WHERE ({predicate})")
        count_row = cursor.fetchone() or {}
        count = int(count_row.get("match_count") or 0)
        cursor.execute(
            "SELECT s.ID AS spell_id, s.SpellName4 AS spell_name, "
            "s.SpellRank4 AS spell_rank "
            f"FROM spell s WHERE ({predicate}) ORDER BY s.ID DESC LIMIT {safe_limit}"
        )
        return SkillConditionPreview(count=count, rows=list(cursor.fetchall()))
    finally:
        cursor.close()
        connection.close()


def load_skill_details(
    profile: DatabaseProfile, feature: Feature, configuration: Any = None
) -> SkillDetails:
    """Read descriptions and the exact DB fields changed by every config group."""
    if not feature.configurable:
        return SkillDetails({}, {}, {})

    module = importlib.import_module(feature.module)
    if configuration is None:
        normalized = feature.default_configuration()
        custom_conditions: dict[str, str] = {}
    else:
        normalized = feature.normalize_configuration(configuration)
        custom_conditions = feature.custom_skill_conditions(normalized, validate=True)
    names = list(
        dict.fromkeys(
            skill
            for group in feature.config_groups
            for skill in normalized[group.config_name]
        )
    )
    if not names:
        return SkillDetails({}, {}, {})
    conditions = dict(module.cond)
    conditions.update(custom_conditions)
    missing_conditions = [name for name in names if name not in conditions]
    if missing_conditions:
        raise ValueError(
            "以下技能缺少查询条件：" + "、".join(missing_conditions)
        )
    conditions = {name: conditions[name] for name in names}
    flags = ", ".join(
        f"(({conditions[name]})) AS skill_match_{index}"
        for index, name in enumerate(names)
    )
    where = " OR ".join(f"({conditions[name]})" for name in names)
    description_expr = (
        "COALESCE(NULLIF(TRIM(s.SpellDescription4), ''), "
        "NULLIF(TRIM(s.SpellToolTip4), ''))"
    )
    spell_columns = f"""
        s.ID AS spell_id,
        s.SpellIconID AS spell_icon_id,
        s.ActiveIconID AS active_icon_id,
        s.SpellName4 AS spell_name,
        {description_expr} AS skill_description,
        s.Effect1 AS effect_1, s.Effect2 AS effect_2, s.Effect3 AS effect_3,
        s.EffectBasePoints1 AS effect_base_points_1,
        s.EffectBasePoints2 AS effect_base_points_2,
        s.EffectBasePoints3 AS effect_base_points_3,
        s.EffectAmplitude1 AS effect_amplitude_1,
        s.EffectAmplitude2 AS effect_amplitude_2,
        s.EffectAmplitude3 AS effect_amplitude_3,
        s.EffectApplyAuraName1 AS effect_apply_aura_1,
        s.EffectApplyAuraName2 AS effect_apply_aura_2,
        s.EffectApplyAuraName3 AS effect_apply_aura_3,
        s.EffectTriggerSpell1 AS effect_trigger_spell_1,
        s.EffectTriggerSpell2 AS effect_trigger_spell_2,
        s.EffectTriggerSpell3 AS effect_trigger_spell_3,
        s.ProcChance AS proc_chance,
        s.ProcCharges AS proc_charges,
        s.DurationIndex AS duration_index,
        s.RecoveryTime AS recovery_time,
        s.CategoryRecoveryTime AS category_recovery_time,
        s.CastingTimeIndex AS casting_time_index,
        s.StartRecoveryCategory AS start_recovery_category,
        s.StartRecoveryTime AS start_recovery_time,
        s.EffectMiscValue1 AS effect_misc_value_1
    """

    connection = mysql.connector.connect(**profile.connector_config())
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            f"SELECT {spell_columns}, {flags} FROM spell s "
            f"WHERE ({where}) ORDER BY s.ID DESC"
        )
        matched_rows: dict[str, list[dict[str, Any]]] = {name: [] for name in names}
        all_rows = cursor.fetchall()
        for row in all_rows:
            for index, name in enumerate(names):
                if row[f"skill_match_{index}"]:
                    matched_rows[name].append(row)

        # Conditions occasionally include a value that this project modifies
        # (for example StartRecoveryTime > 0). If a prior run makes that
        # condition false, fall back to the stable spell display name so the UI
        # can still show the new current value.
        patterns = {name: _fallback_pattern(name, conditions[name]) for name in names}
        unique_patterns = list(dict.fromkeys(patterns.values()))
        fallback_rows: list[dict[str, Any]] = []
        if unique_patterns:
            clauses = " OR ".join(["s.SpellName4 LIKE %s"] * len(unique_patterns))
            cursor.execute(
                f"SELECT {spell_columns} FROM spell s WHERE {clauses} ORDER BY s.ID DESC",
                tuple(unique_patterns),
            )
            fallback_rows = cursor.fetchall()

        descriptions: dict[str, str] = {}
        rows_by_skill: dict[str, list[dict[str, Any]]] = {}
        for name in names:
            fallback_for_name = [
                row
                for row in fallback_rows
                if _matches_pattern(str(row["spell_name"] or ""), patterns[name])
            ]
            rows = matched_rows[name] or fallback_for_name
            rows_by_skill[name] = rows
            for row in matched_rows[name] + fallback_for_name:
                description = _clean_description(row["skill_description"])
                if description:
                    descriptions[name] = description
                    break

        raw_values: dict[tuple[str, str], list[Any]] = {}
        trigger_ids: dict[tuple[str, str], set[int]] = {}
        enchant_ids: dict[tuple[str, str], set[int]] = {}
        duration_indexes: set[int] = set()
        cast_indexes: set[int] = set()

        for group in feature.config_groups:
            group_name = group.config_name
            for name in normalized[group_name]:
                key = (group_name, name)
                values: list[Any] = []
                for row in rows_by_skill[name]:
                    if group.function == "mod_dmg":
                        values.extend(_effect_base_values(row, 2))
                    elif group.function == "mod_talent_extra_attack":
                        values.extend(_effect_base_values(row, 19))
                    elif group.function == "mod_talent_dummy":
                        values.extend(_effect_base_values(row, 3))
                    elif group.function == "mod_talent":
                        values.extend(_effect_base_values(row, 6))
                    elif group.function == "mod_dot_interval":
                        for slot in range(1, 4):
                            amplitude = row[f"effect_amplitude_{slot}"]
                            if row[f"effect_{slot}"] == 6 and amplitude not in (None, -1, 0):
                                values.append(amplitude)
                    elif group.function == "mod_trigger_chance":
                        if _has_trigger_aura(row, (42, 4)) and row["proc_chance"] not in (None, -1, 0):
                            values.append(row["proc_chance"])
                    elif group.function == "mod_duration":
                        if row["duration_index"] is not None:
                            values.append(row["duration_index"])
                            duration_indexes.add(int(row["duration_index"]))
                    elif group.function == "mod_trigger_time":
                        if _has_trigger_aura(row, (42,)) and row["proc_charges"] is not None:
                            values.append(row["proc_charges"])
                    elif group.function == "mod_cooldown_time":
                        if row["recovery_time"] == 0 and row["category_recovery_time"] not in (None, 0):
                            values.append(row["category_recovery_time"])
                    elif group.function == "mod_cast_time":
                        if row["casting_time_index"] is not None:
                            values.append(row["casting_time_index"])
                            cast_indexes.add(int(row["casting_time_index"]))
                    elif group.function == "mod_gcd_time":
                        if row["start_recovery_time"] is not None:
                            values.append(row["start_recovery_time"])
                    elif group.function == "mod_trigger":
                        trigger_id = row["effect_trigger_spell_1"]
                        if trigger_id and trigger_id > 0:
                            trigger_ids.setdefault(key, set()).add(int(trigger_id))
                    elif group.function == "mod_enchant_spell_trigger_chance":
                        enchant_id = row["effect_misc_value_1"]
                        if enchant_id and enchant_id > 0:
                            enchant_ids.setdefault(key, set()).add(int(enchant_id))
                raw_values[key] = values

        all_trigger_ids = set().union(*trigger_ids.values()) if trigger_ids else set()
        if all_trigger_ids:
            placeholders = ", ".join(["%s"] * len(all_trigger_ids))
            cursor.execute(
                f"SELECT {spell_columns} FROM spell s WHERE s.ID IN ({placeholders})",
                tuple(sorted(all_trigger_ids)),
            )
            target_rows = {int(row["spell_id"]): row for row in cursor.fetchall()}
            for key, ids in trigger_ids.items():
                for spell_id in ids:
                    row = target_rows.get(spell_id)
                    if row:
                        raw_values[key].extend(_effect_base_values(row, 6))

        all_enchant_ids = set().union(*enchant_ids.values()) if enchant_ids else set()
        if all_enchant_ids:
            cursor.execute("SHOW COLUMNS FROM spellitemenchantment")
            enchant_columns = {
                str(row.get("Field") or row.get("field") or "").lower():
                str(row.get("Field") or row.get("field") or "")
                for row in cursor.fetchall()
            }
            point_columns = []
            for slot in range(1, 4):
                candidates = (f"effectpointsmin_{slot}", f"minamount{slot}")
                column = next(
                    (enchant_columns[name] for name in candidates if name in enchant_columns),
                    None,
                )
                if column is None:
                    raise RuntimeError(
                        f"spellitemenchantment 缺少第 {slot} 个附魔数值字段"
                    )
                point_columns.append(column)
            placeholders = ", ".join(["%s"] * len(all_enchant_ids))
            point_select = ", ".join(
                f"{column} AS point_{slot}"
                for slot, column in enumerate(point_columns, start=1)
            )
            cursor.execute(
                f"SELECT ID AS enchant_id, {point_select} "
                f"FROM spellitemenchantment WHERE ID IN ({placeholders})",
                tuple(sorted(all_enchant_ids)),
            )
            enchant_rows = {int(row["enchant_id"]): row for row in cursor.fetchall()}
            for key, ids in enchant_ids.items():
                for enchant_id in ids:
                    row = enchant_rows.get(enchant_id)
                    if row:
                        points = [row[f"point_{slot}"] for slot in range(1, 4)]
                        nonzero = [value for value in points if value not in (None, 0)]
                        raw_values[key].extend(nonzero or [0])

        duration_values = _lookup_index_values(
            cursor, "spellduration", "BaseDuration", duration_indexes
        )
        cast_values = _lookup_index_values(
            cursor, "spellcasttimes", "CastingTime", cast_indexes
        )
        duration_labels = _code_index_labels("mod_duration", "duration_dict")
        cast_labels = _code_index_labels("mod_cast_time_with_condition", "cast_time_dict")

        current_values: dict[tuple[str, str], str] = {}
        groups = {group.config_name: group for group in feature.config_groups}
        for key, values in raw_values.items():
            function = groups[key[0]].function
            if function in {"mod_dot_interval", "mod_cooldown_time", "mod_gcd_time"}:
                current_values[key] = _format_values(values, _format_milliseconds)
            elif function == "mod_trigger_chance":
                current_values[key] = _format_values(values, lambda value: f"{_format_number(value)}%")
            elif function == "mod_duration":
                current_values[key] = _format_index_values(values, duration_values, duration_labels)
            elif function == "mod_cast_time":
                current_values[key] = _format_index_values(values, cast_values, cast_labels)
            else:
                current_values[key] = _format_values(values)

        icons: dict[str, SkillIconReference] = {}
        for name, rows in rows_by_skill.items():
            for row in rows:
                icon_id = int(row.get("spell_icon_id") or 0)
                active_icon_id = int(row.get("active_icon_id") or 0)
                if icon_id or active_icon_id:
                    icons[name] = SkillIconReference(
                        spell_id=int(row.get("spell_id") or 0),
                        spell_icon_id=icon_id,
                        active_icon_id=active_icon_id,
                    )
                    break

        return SkillDetails(
            {name: descriptions.get(name, "") for name in names},
            {key: current_values.get(key, "") for key in raw_values},
            icons,
        )
    finally:
        cursor.close()
        connection.close()


def load_skill_descriptions(
    profile: DatabaseProfile, feature: Feature, configuration: Any = None
) -> dict[str, str]:
    """Backward-compatible description-only facade."""
    return load_skill_details(profile, feature, configuration).descriptions
