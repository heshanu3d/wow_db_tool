from __future__ import annotations

import hashlib
import importlib
import inspect
import json
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SkillConfigGroup:
    config_name: str
    title: str
    function: str
    value_label: str
    description: str = ""


@dataclass(frozen=True)
class Feature:
    id: str
    title: str
    category: str
    description: str
    module: str
    function: str = "customize"
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)
    action_kind: str = "function"
    config_name: str = ""
    risk: str = "normal"
    notes: str = ""
    config_groups: tuple[SkillConfigGroup, ...] = ()

    @cached_property
    def version(self) -> str:
        module = importlib.import_module(self.module)
        source_path = inspect.getsourcefile(module)
        source = Path(source_path).read_bytes() if source_path else repr(module).encode()
        identity = json.dumps(
            {
                "function": self.function,
                "args": self.args,
                "kwargs": self.kwargs,
                "action_kind": self.action_kind,
                "config_name": self.config_name,
                "config_groups": [group.__dict__ for group in self.config_groups],
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(source + identity).hexdigest()[:12]

    @property
    def configurable(self) -> bool:
        return bool(self.config_groups)

    def default_configuration(self) -> dict[str, dict[str, dict[str, Any]]]:
        module = importlib.import_module(self.module)
        return {
            group.config_name: {
                skill: {"enabled": True, "value": str(value)}
                for skill, value in getattr(module, group.config_name).items()
            }
            for group in self.config_groups
        }

    def normalize_configuration(self, configuration: Any = None) -> dict[str, dict[str, dict[str, Any]]]:
        defaults = self.default_configuration()
        source = configuration if isinstance(configuration, dict) else {}
        normalized: dict[str, dict[str, dict[str, Any]]] = {}
        for group in self.config_groups:
            saved_group = source.get(group.config_name, {})
            if not isinstance(saved_group, dict):
                saved_group = {}
            normalized[group.config_name] = {}
            for skill, default_item in defaults[group.config_name].items():
                saved_item = saved_group.get(skill, {})
                if isinstance(saved_item, dict):
                    enabled = bool(saved_item.get("enabled", default_item["enabled"]))
                    value = saved_item.get("value", default_item["value"])
                elif saved_item not in ({}, None):
                    enabled = True
                    value = saved_item
                else:
                    enabled = default_item["enabled"]
                    value = default_item["value"]
                normalized[group.config_name][skill] = {
                    "enabled": enabled,
                    "value": str(value),
                }
        return normalized

    def configured_values(self, configuration: Any = None) -> dict[str, dict[str, Any]]:
        module = importlib.import_module(self.module)
        normalized = self.normalize_configuration(configuration)
        result: dict[str, dict[str, Any]] = {}
        for group in self.config_groups:
            defaults = getattr(module, group.config_name)
            values: dict[str, Any] = {}
            for skill, item in normalized[group.config_name].items():
                if not item["enabled"]:
                    continue
                raw = item["value"].strip()
                if not raw:
                    raise ValueError(f"{group.title} / {skill}：修改值不能为空。")
                default = defaults[skill]
                try:
                    if isinstance(default, bool):
                        value = raw.lower() in ("1", "true", "yes", "on")
                    elif isinstance(default, int):
                        value = int(raw)
                    elif isinstance(default, float):
                        value = float(raw)
                    else:
                        value = raw
                except ValueError as exc:
                    expected = "整数" if isinstance(default, int) else "数字"
                    raise ValueError(f"{group.title} / {skill}：请输入有效的{expected}。") from exc
                values[skill] = value
            result[group.config_name] = values
        return result

    def configuration_summary(self, configuration: Any = None) -> tuple[int, int]:
        normalized = self.normalize_configuration(configuration)
        total = sum(len(items) for items in normalized.values())
        enabled = sum(
            1
            for items in normalized.values()
            for item in items.values()
            if item["enabled"]
        )
        return enabled, total

    def effective_version(self, configuration: Any = None) -> str:
        if not self.configurable:
            return self.version
        normalized = self.normalize_configuration(configuration)
        payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256(self.version.encode("ascii") + payload).hexdigest()[:12]

    def execute(self, instance: Any, configuration: Any = None) -> Any:
        module = importlib.import_module(self.module)
        if self.action_kind == "spell_bundle":
            from src.customization.base import spell

            mod = spell.Mod(instance, module.cond)
            configured = self.configured_values(configuration)
            for group in self.config_groups:
                values = configured[group.config_name]
                if not values:
                    continue
                print(f"[{group.title}] 应用 {len(values)} 个技能配置")
                for skill, value in values.items():
                    print(f"  - {skill}: {value}")
                getattr(mod, group.function)(values)
            return None
        if self.action_kind == "spell_mod":
            from src.customization.base import spell

            mod = spell.Mod(instance, module.cond)
            method = getattr(mod, self.function)
            config = getattr(module, self.config_name)
            return method(config, *self.args, **self.kwargs)
        if self.action_kind == "mysql_method":
            return getattr(instance, self.function)(*self.args, **self.kwargs)
        function = getattr(module, self.function)
        return function(instance, *self.args, **self.kwargs)


DK_CONFIG_GROUPS = (
    SkillConfigGroup("mod_gcd_time_skills", "公共冷却时间（GCD）", "mod_gcd_time", "毫秒", "0 表示无 GCD。"),
    SkillConfigGroup("mod_duration_skills", "技能持续时间", "mod_duration", "时长", "使用代码中的时长格式，例如 300s。"),
    SkillConfigGroup("mod_talent_skills", "天赋效果倍率", "mod_talent", "倍率"),
    SkillConfigGroup("mod_trigger_chance_skills", "触发几率倍率", "mod_trigger_chance", "倍率"),
)

PRIEST_CONFIG_GROUPS = (
    SkillConfigGroup("mod_gcd_time_skills", "公共冷却时间（GCD）", "mod_gcd_time", "毫秒", "0 表示无 GCD。"),
    SkillConfigGroup("mod_duration_skills", "技能持续时间", "mod_duration", "时长", "使用代码中的时长格式，例如 1800s。"),
    SkillConfigGroup("mod_talent_skills", "天赋效果倍率", "mod_talent", "倍率"),
    SkillConfigGroup("mod_trigger_chance_skills", "触发几率倍率", "mod_trigger_chance", "倍率"),
)

ROGUE_CONFIG_GROUPS = (
    SkillConfigGroup("mod_gcd_time_skills", "公共冷却时间（GCD）", "mod_gcd_time", "毫秒", "0 表示无 GCD。"),
)

SHAMAN_CONFIG_GROUPS = (
    SkillConfigGroup("mod_dmg_skills", "技能伤害与治疗", "mod_dmg", "倍率"),
    SkillConfigGroup("mod_talent_skills", "天赋效果", "mod_talent", "倍率"),
    SkillConfigGroup("mod_talent_dummy_skills", "Dummy 天赋效果", "mod_talent_dummy", "倍率"),
    SkillConfigGroup("mod_talent_extra_attack_skills", "额外攻击次数", "mod_talent_extra_attack", "倍率"),
    SkillConfigGroup("mod_dot_interval_skills", "持续伤害间隔", "mod_dot_interval", "倍率"),
    SkillConfigGroup("mod_trigger_chance_skills", "技能触发几率", "mod_trigger_chance", "倍率"),
    SkillConfigGroup("mod_duration_skills", "技能持续时间", "mod_duration", "时长"),
    SkillConfigGroup("mod_trigger_time_skills", "触发次数", "mod_trigger_time", "次数"),
    SkillConfigGroup("mod_cooldown_time_skills", "技能冷却时间", "mod_cooldown_time", "毫秒"),
    SkillConfigGroup("mod_cast_time_skills", "技能施法时间", "mod_cast_time", "时长"),
    SkillConfigGroup("mod_gcd_time_skills", "公共冷却时间（GCD）", "mod_gcd_time", "毫秒"),
    SkillConfigGroup("mod_trigger_skills", "触发技能效果", "mod_trigger", "倍率"),
    SkillConfigGroup("mod_enchant_spell_trigger_chance_skills", "武器附魔触发率", "mod_enchant_spell_trigger_chance", "倍率"),
)


# 每一项都是一个可独立执行、可追踪状态的数据库功能。倍率类功能重复执行会继续叠加，
# 因此 GUI 在重新应用时会进行二次确认。
FEATURES: tuple[Feature, ...] = (
    Feature("creature.locale.zh", "汉化生物名称", "世界与任务", "把 locales_creature 的中文名称写回 creature_template。", "src.customization.creature.common", "creature_template_localeZH"),
    Feature("creature.custom_vendor", "创建自定义免费商人", "世界与任务", "重建项目中配置的自定义商人，并加入免费图腾等物品。", "src.customization.creature.vendor", risk="high", notes="会先删除相同 entry 的旧 NPC。"),
    Feature("dungeon.no_requirements", "取消副本进入限制", "世界与任务", "清除副本的成就、任务和物品进入条件。", "src.customization.dungeon.common", "remove_dungeon_requirements", risk="high"),
    Feature("quest.cap_requirements", "降低任务收集数量", "世界与任务", "将任务所需物品和目标数量统一限制到 2 个。", "src.customization.quest.common", "mod_quest_request_item_count"),

    Feature("item.locale.zh", "汉化物品名称与描述", "物品与装备", "把 locales_item 中的中文名称、描述写回 item_template。", "src.customization.item.common", "item_template_localeZH_1"),
    Feature("item.stack.255", "物品堆叠上限 255", "物品与装备", "将当前可堆叠物品的最大堆叠数量统一调整为 255。", "src.customization.item.common", "mod_stackable_item", (255,)),
    Feature("equipment.remove_unique", "移除装备唯一限制", "物品与装备", "移除武器和装备的唯一属性限制。", "src.customization.item.equipment", "remove_unique_attr_on_equip", risk="high"),
    Feature("equipment.generate_upgrade_v1", "生成装备强化数据 V1", "物品与装备", "生成蓝装、紫装强化所需的 item_template 与 item_up 数据。", "src.customization.item.equipment", "gen_item_update_v1", risk="high", notes="生成型功能，执行前建议备份相关表。"),
    Feature("jewel.clear_upgrade", "清除强化宝石数据", "物品与装备", "删除脚本生成的强化宝石、附魔及 item_up 数据。", "src.customization.profession.jewel", "del_update_jewel_dbinfo", risk="high"),
    Feature("jewel.generate_upgrade", "生成强化宝石数据", "物品与装备", "以 2 倍递进规则生成蓝/紫宝石 +1 到 +5 数据。", "src.customization.profession.jewel", "apply_jewel_update", (2,), risk="high", notes="会生成 SQL 文件并将 all.sql 对应数据直接写入当前数据库。"),

    Feature("profession.fast_cast", "专业技能快速施法", "专业技能", "采集、熔炼、剥皮、采药、分解即时完成，图纸和专业技能施法缩短到 250ms，钓鱼缩短。", "src.customization.profession.common"),
    Feature("profession.alchemy.x25", "药剂效果 ×25", "专业技能", "将药剂相关 SpellItemEnchantment 效果放大 25 倍。", "src.customization.profession.alchemy", "multi_effect_on_potion", (25,), risk="high"),
    Feature("profession.enchant.x20", "附魔效果 ×20", "专业技能", "将项目识别到的附魔效果放大 20 倍。", "src.customization.profession.enchantment", "muiti_enchantment_spell", (20,), risk="high"),
    Feature("profession.scroll.x5", "卷轴效果 ×5", "专业技能", "将卷轴类效果放大 5 倍。", "src.customization.profession.inscription", "multi_effect_on_scroll", (5,), risk="high"),
    Feature("profession.master_inscription.x15", "大师铭文效果 ×15", "专业技能", "将大师的铭文类附魔效果放大 15 倍。", "src.customization.profession.inscription", "muiti_master_inspiration", (15,), risk="high"),

    Feature(
        "class.dk.bundle", "死亡骑士", "职业技能",
        "逐项配置死亡骑士的 GCD、持续时间、天赋倍率和触发几率。",
        "src.customization.spell.dk", action_kind="spell_bundle", risk="high",
        config_groups=DK_CONFIG_GROUPS,
    ),
    Feature(
        "class.priest.bundle", "牧师", "职业技能",
        "逐项配置牧师的 GCD、持续时间、天赋倍率和触发几率。",
        "src.customization.spell.priest", action_kind="spell_bundle", risk="high",
        config_groups=PRIEST_CONFIG_GROUPS,
    ),
    Feature(
        "class.rogue.bundle", "盗贼", "职业技能",
        "逐项配置盗贼技能的公共冷却时间。",
        "src.customization.spell.rogue", action_kind="spell_bundle", risk="high",
        config_groups=ROGUE_CONFIG_GROUPS,
    ),
    Feature(
        "class.shaman.bundle", "萨满祭司", "职业技能",
        "逐项配置萨满的伤害、天赋、持续时间、冷却、施法时间和触发效果。",
        "src.customization.spell.shaman", action_kind="spell_bundle", risk="high",
        config_groups=SHAMAN_CONFIG_GROUPS,
    ),
    Feature("class.shaman.weapon_duration", "元素武器持续时间 ×12", "萨满增强", "将石化、火舌、冰封和风怒武器持续时间放大 12 倍。", "src.customization.spell.shaman", "mod_element_weapon_duration", (12,), risk="high"),
    Feature("class.shaman.two_hand", "萨满双手武器描述", "萨满增强", "修改双手斧和锤相关技能数据及中文描述。", "src.customization.spell.shaman", "mod_spell_16269", risk="high"),

    Feature("tools.generate_item_csv", "生成 item DBC 源 CSV", "数据工具", "根据 item_template 重建 item 表，并导出 item.csv 供 DBC 工具使用。", "src.core.mysql_core", "gen_item_csv", action_kind="mysql_method", risk="high"),
)

FEATURE_BY_ID = {feature.id: feature for feature in FEATURES}
CATEGORIES = tuple(dict.fromkeys(feature.category for feature in FEATURES))
