from __future__ import annotations

import importlib
from typing import Any

import mysql.connector

from .config import DatabaseProfile
from .features import Feature


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


def load_skill_descriptions(profile: DatabaseProfile, feature: Feature) -> dict[str, str]:
    """Read the best matching Chinese description for every configured skill.

    The conditions are the same trusted conditions used by the modification
    code. One SELECT scans the spell table and returns a boolean match column
    for every skill, avoiding one database round-trip per skill.
    """
    if not feature.configurable:
        return {}

    module = importlib.import_module(feature.module)
    names = skill_names(feature)
    conditions = [module.cond[name] for name in names]
    if not names:
        return {}

    description_expr = (
        "COALESCE(NULLIF(TRIM(s.SpellDescription4), ''), "
        "NULLIF(TRIM(s.SpellToolTip4), ''))"
    )
    flags = ", ".join(
        f"(({condition})) AS skill_match_{index}"
        for index, condition in enumerate(conditions)
    )
    where = " OR ".join(f"({condition})" for condition in conditions)
    sql = f"""
        SELECT s.id, {description_expr} AS skill_description, {flags}
        FROM spell s
        WHERE {description_expr} IS NOT NULL
          AND ({where})
        ORDER BY s.id DESC
    """

    connection = mysql.connector.connect(**profile.connector_config())
    cursor = connection.cursor()
    try:
        cursor.execute(sql)
        descriptions: dict[str, str] = {}
        for row in cursor.fetchall():
            description = _clean_description(row[1])
            if not description:
                continue
            for index, matched in enumerate(row[2:]):
                name = names[index]
                if matched and name not in descriptions:
                    descriptions[name] = description

        # Some configuration entries target an effect row whose own DBC
        # description is blank. Fall back to the highest-ranked spell with the
        # same display name (and strip the project's `_效果` helper suffix).
        missing = [name for name in names if name not in descriptions]
        lookup_names = list(dict.fromkeys(name.removesuffix("_效果") for name in missing))
        if lookup_names:
            placeholders = ", ".join(["%s"] * len(lookup_names))
            fallback_sql = f"""
                SELECT s.SpellName4, {description_expr} AS skill_description
                FROM spell s
                WHERE s.SpellName4 IN ({placeholders})
                  AND {description_expr} IS NOT NULL
                ORDER BY s.id DESC
            """
            cursor.execute(fallback_sql, tuple(lookup_names))
            by_display_name: dict[str, str] = {}
            for display_name, raw_description in cursor.fetchall():
                description = _clean_description(raw_description)
                if description and display_name not in by_display_name:
                    by_display_name[display_name] = description
            for name in missing:
                description = by_display_name.get(name.removesuffix("_效果"), "")
                if description:
                    descriptions[name] = description

        return {name: descriptions.get(name, "") for name in names}
    finally:
        cursor.close()
        connection.close()
