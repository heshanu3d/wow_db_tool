from __future__ import annotations

import copy
import importlib
import os
import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QPoint, QPointF, Qt
from PyQt5.QtGui import QWheelEvent
from PyQt5.QtWidgets import QApplication, QLabel, QPushButton, QWidget

QT_APPLICATION = QApplication.instance() or QApplication([])

from PIL import Image

from src.core.mysql_core import Mysql
from src.customization.base import spell
from src.gui.app import (
    CUSTOM_SKILL_EDITOR_GEOMETRY_KEY,
    CUSTOM_SKILLS_DIALOG_GEOMETRY_KEY,
    CustomSkillEditorDialog,
    CustomSkillsDialog,
    DbToolApp,
    ProfilesDialog,
    ScrollFrame,
    SkillConfigView,
)
from src.gui.config import AppSettings, DatabaseProfile, load_settings, save_settings
from src.gui.features import (
    CUSTOM_SKILL_CONDITIONS_KEY,
    FEATURE_BY_ID,
    FEATURES,
    SKILL_CONDITION_TEMPLATE_BY_TITLE,
    SKILL_CONDITION_TEMPLATES,
    Feature,
    SkillConfigGroup,
    validate_skill_condition,
)
from src.gui.runner import run_feature
from src.gui.skill_descriptions import load_skill_details, preview_skill_condition, skill_names
from src.gui.spell_icons import (
    SkillIconReference,
    SpellIconCache,
    SpellIconSyncResult,
    get_spell_icon_path,
    load_spell_icon_dbc,
    spell_icon_resource_directories,
    suggested_spell_icon_paths,
)
from src.gui.state import FeatureStateStore


class GuiFoundationTests(unittest.TestCase):
    def test_feature_ids_are_unique_and_actions_exist(self):
        ids = [feature.id for feature in FEATURES]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(len(FEATURES), 20)
        self.assertEqual(
            {feature.id for feature in FEATURES if feature.category == "职业技能"},
            {"class.dk.bundle", "class.priest.bundle", "class.rogue.bundle", "class.shaman.bundle"},
        )
        expected_skill_counts = {
            "class.dk.bundle": 47,
            "class.priest.bundle": 65,
            "class.rogue.bundle": 29,
            "class.shaman.bundle": 89,
        }
        for feature in FEATURES:
            module = importlib.import_module(feature.module)
            self.assertEqual(len(feature.version), 12)
            if feature.action_kind == "spell_bundle":
                self.assertTrue(feature.configurable)
                self.assertIsInstance(module.cond, dict)
                defaults = feature.default_configuration()
                self.assertEqual(
                    sum(len(group) for group in defaults.values()),
                    expected_skill_counts[feature.id],
                )
                self.assertEqual(len(feature.config_groups), 13)
                for group in feature.config_groups:
                    values = getattr(module, group.config_name, {})
                    self.assertIsInstance(values, dict)
                    self.assertTrue(callable(getattr(spell.Mod, group.function)))
                    self.assertEqual(
                        {skill: item["value"] for skill, item in defaults[group.config_name].items()},
                        {skill: str(value) for skill, value in values.items()},
                    )
                    self.assertTrue(
                        set(values).issubset(module.cond),
                        f"{feature.title}/{group.title} 中存在无法匹配 cond 的技能",
                    )
            elif feature.action_kind == "spell_mod":
                self.assertTrue(hasattr(module, "cond"))
                self.assertTrue(hasattr(module, feature.config_name))
            elif feature.action_kind == "mysql_method":
                self.assertTrue(callable(getattr(Mysql, feature.function)))
            else:
                self.assertTrue(callable(getattr(module, feature.function)))

    def test_skill_configuration_defaults_and_value_conversion(self):
        feature = FEATURE_BY_ID["class.dk.bundle"]
        config = feature.default_configuration()
        self.assertEqual(config["mod_gcd_time_skills"]["传染"], {"enabled": True, "value": "0"})

        config["mod_gcd_time_skills"]["传染"] = {"enabled": True, "value": "123"}
        config["mod_gcd_time_skills"]["凛风冲击"]["enabled"] = False
        config["mod_talent_skills"]["邪恶虫群"] = {"enabled": True, "value": "2.75"}
        values = feature.configured_values(config)

        self.assertEqual(values["mod_gcd_time_skills"]["传染"], 123)
        self.assertNotIn("凛风冲击", values["mod_gcd_time_skills"])
        self.assertEqual(values["mod_talent_skills"]["邪恶虫群"], 2.75)
        self.assertIsInstance(values["mod_talent_skills"]["邪恶虫群"], float)

    def test_invalid_skill_configuration_is_rejected(self):
        feature = FEATURE_BY_ID["class.dk.bundle"]
        config = feature.default_configuration()
        config["mod_gcd_time_skills"]["传染"]["value"] = "not-an-integer"
        with self.assertRaisesRegex(ValueError, "请输入有效的整数"):
            feature.configured_values(config)

    def test_skill_configuration_changes_effective_version(self):
        feature = FEATURE_BY_ID["class.dk.bundle"]
        original = feature.default_configuration()
        modified = copy.deepcopy(original)
        modified["mod_gcd_time_skills"]["传染"]["value"] = "123"
        self.assertEqual(len(feature.effective_version(original)), 12)
        self.assertNotEqual(feature.effective_version(original), feature.effective_version(modified))

    def test_spell_bundle_executes_only_checked_skills_without_database(self):
        feature = FEATURE_BY_ID["class.dk.bundle"]
        config = feature.default_configuration()
        for group in config.values():
            for item in group.values():
                item["enabled"] = False
        config["mod_gcd_time_skills"]["传染"] = {"enabled": True, "value": "123"}
        instance = Mock(name="mysql_instance")

        with patch("src.customization.base.spell.Mod") as mod_class, patch("builtins.print"):
            feature.execute(instance, config)

        module = importlib.import_module(feature.module)
        mod_class.assert_called_once_with(instance, module.cond)
        mod = mod_class.return_value
        mod.mod_gcd_time.assert_called_once_with({"传染": 123})
        mod.mod_duration.assert_not_called()
        mod.mod_talent.assert_not_called()
        mod.mod_trigger_chance.assert_not_called()

    def test_custom_skill_configuration_is_normalized_and_typed(self):
        feature = FEATURE_BY_ID["class.dk.bundle"]
        config = feature.default_configuration()
        condition = "s.SpellName4='测试自定义技能' and s.ID=12345"
        config[CUSTOM_SKILL_CONDITIONS_KEY] = {"测试自定义技能": condition}
        config["mod_gcd_time_skills"]["测试自定义技能"] = {
            "enabled": True,
            "value": "250",
        }
        config["mod_duration_skills"]["测试自定义技能"] = {
            "enabled": True,
            "value": "30s",
        }
        config["mod_talent_skills"]["测试自定义技能"] = {
            "enabled": True,
            "value": "2.5",
        }

        normalized = feature.normalize_configuration(config)
        values = feature.configured_values(normalized)

        self.assertEqual(
            normalized[CUSTOM_SKILL_CONDITIONS_KEY],
            {"测试自定义技能": condition},
        )
        self.assertEqual(values["mod_gcd_time_skills"]["测试自定义技能"], 250)
        self.assertEqual(values["mod_duration_skills"]["测试自定义技能"], "30s")
        self.assertEqual(values["mod_talent_skills"]["测试自定义技能"], 2.5)
        enabled, total = feature.configuration_summary(normalized)
        self.assertEqual(total, sum(len(normalized[g.config_name]) for g in feature.config_groups))
        self.assertGreaterEqual(enabled, 3)

    def test_skill_condition_templates_render_common_cond_patterns(self):
        self.assertGreaterEqual(len(SKILL_CONDITION_TEMPLATES), 10)
        titles = [template.title for template in SKILL_CONDITION_TEMPLATES]
        self.assertEqual(len(titles), len(set(titles)))
        self.assertEqual(
            SKILL_CONDITION_TEMPLATE_BY_TITLE["技能名称 + 全部等级"].render(
                "死亡之握"
            ),
            "s.SpellName4='死亡之握' and s.SpellRank4 like '等级%'",
        )
        self.assertEqual(
            SKILL_CONDITION_TEMPLATE_BY_TITLE["精确技能名称"].render("测试'技能"),
            "s.SpellName4='测试''技能'",
        )
        for template in SKILL_CONDITION_TEMPLATES:
            self.assertNotIn("{skill}", template.render("测试技能"))
            validate_skill_condition(template.render("测试技能"))

    def test_all_classes_offer_the_same_modification_types(self):
        class_features = [
            feature for feature in FEATURES if feature.action_kind == "spell_bundle"
        ]
        expected = [
            group.config_name for group in class_features[0].config_groups
        ]
        self.assertEqual(len(expected), 13)
        for feature in class_features:
            self.assertEqual(
                [group.config_name for group in feature.config_groups], expected
            )
            defaults = feature.default_configuration()
            self.assertEqual(list(defaults), expected)

    def test_custom_skill_condition_rejects_unsafe_sql_and_code_name_collision(self):
        self.assertEqual(
            validate_skill_condition("s.SpellName4='测试技能' and s.ID=123"),
            "s.SpellName4='测试技能' and s.ID=123",
        )
        for condition in (
            "1=1; DROP TABLE spell",
            "s.ID=1 -- comment",
            "s.ID IN (SELECT ID FROM spell)",
        ):
            with self.subTest(condition=condition), self.assertRaises(ValueError):
                validate_skill_condition(condition)

        feature = FEATURE_BY_ID["class.dk.bundle"]
        config = feature.default_configuration()
        config[CUSTOM_SKILL_CONDITIONS_KEY] = {"传染": "s.ID=50842"}
        with self.assertRaisesRegex(ValueError, "与代码 cond 定义重复"):
            feature.configured_values(config)

    def test_spell_bundle_executes_gui_defined_skill_condition(self):
        feature = FEATURE_BY_ID["class.dk.bundle"]
        config = feature.default_configuration()
        for group in config.values():
            for item in group.values():
                item["enabled"] = False
        condition = "s.SpellName4='测试自定义技能' and s.ID=12345"
        config[CUSTOM_SKILL_CONDITIONS_KEY] = {"测试自定义技能": condition}
        config["mod_gcd_time_skills"]["测试自定义技能"] = {
            "enabled": True,
            "value": "250",
        }
        instance = Mock(name="mysql_instance")

        with patch("src.customization.base.spell.Mod") as mod_class, patch("builtins.print"):
            feature.execute(instance, config)

        module = importlib.import_module(feature.module)
        expected_conditions = dict(module.cond)
        expected_conditions["测试自定义技能"] = condition
        mod_class.assert_called_once_with(instance, expected_conditions)
        mod_class.return_value.mod_gcd_time.assert_called_once_with(
            {"测试自定义技能": 250}
        )

    def test_custom_skill_settings_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            custom = {
                "class.dk.bundle": {
                    "mod_gcd_time_skills": {
                        "测试自定义技能": {"enabled": True, "value": "250"}
                    },
                    CUSTOM_SKILL_CONDITIONS_KEY: {
                        "测试自定义技能": "s.SpellName4='测试自定义技能' and s.ID=12345"
                    },
                }
            }
            save_settings(
                AppSettings(
                    profiles=[DatabaseProfile("测试")], feature_configs=custom
                ),
                path,
            )
            self.assertEqual(load_settings(path).feature_configs, custom)

    def test_save_settings_retains_loadable_rolling_backups(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".db_tool_gui.json"
            original = AppSettings(
                profiles=[DatabaseProfile("原连接", "old-host", password="old-secret")],
                feature_configs={"feature": {"group": {"skill": {"value": "1"}}}},
            )
            replacement = AppSettings(
                profiles=[DatabaseProfile("新连接", "new-host", password="new-secret")]
            )
            save_settings(original, path)
            save_settings(replacement, path)

            backups = list((Path(directory) / ".db_tool_gui_backups").glob("*.json"))
            self.assertEqual(len(backups), 1)
            recovered = load_settings(backups[0])
            self.assertEqual(recovered.profiles[0].name, "原连接")
            self.assertEqual(recovered.profiles[0].host, "old-host")
            self.assertTrue(recovered.feature_configs)
            self.assertEqual(load_settings(path).profiles[0].name, "新连接")

    def test_settings_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            feature_config = {
                "class.dk.bundle": {
                    "mod_gcd_time_skills": {
                        "传染": {"enabled": True, "value": "123"},
                    }
                }
            }
            settings = AppSettings(
                profiles=[DatabaseProfile("测试", "db.example", 3307, "wow", "secret", "world")],
                selected_profile=0,
                window_geometry="1100x720",
                feature_configs=feature_config,
                dialog_geometries={
                    CUSTOM_SKILLS_DIALOG_GEOMETRY_KEY: "940x560+30+40"
                },
                spell_icon_dbc_path="/tmp/SpellIcon.dbc",
                spell_icon_client_root="/tmp/wow-client",
            )
            save_settings(settings, path)
            loaded = load_settings(path)
            self.assertEqual(loaded.window_geometry, "1100x720")
            self.assertEqual(
                loaded.dialog_geometries,
                {CUSTOM_SKILLS_DIALOG_GEOMETRY_KEY: "940x560+30+40"},
            )
            self.assertEqual(loaded.profiles[0].target_label, "wow@db.example:3307/world")
            self.assertEqual(loaded.profiles[0].connector_config()["password"], "secret")
            self.assertEqual(loaded.feature_configs, feature_config)
            self.assertEqual(loaded.spell_icon_dbc_path, "/tmp/SpellIcon.dbc")
            self.assertEqual(loaded.spell_icon_client_root, "/tmp/wow-client")

    def test_save_dialog_geometry_updates_only_the_requested_layout(self):
        app = SimpleNamespace(
            settings=AppSettings(
                profiles=[DatabaseProfile("测试")],
                dialog_geometries={"another_dialog": "500x400+1+2"},
            )
        )

        with patch("src.gui.app.save_settings") as persist:
            DbToolApp.save_dialog_geometry(
                app, CUSTOM_SKILLS_DIALOG_GEOMETRY_KEY, "940x560+30+40"
            )

        persist.assert_called_once_with(app.settings)
        self.assertEqual(
            app.settings.dialog_geometries,
            {
                "another_dialog": "500x400+1+2",
                CUSTOM_SKILLS_DIALOG_GEOMETRY_KEY: "940x560+30+40",
            },
        )


    def test_suggested_spell_icon_paths_prefers_bundled_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            dbc_file = (
                project_root
                / "assets"
                / "wow_335"
                / "DBC_335_wotlk"
                / "SpellIcon.dbc"
            )
            spellbook = project_root / "assets" / "Interface" / "Spellbook"
            dbc_file.parent.mkdir(parents=True)
            spellbook.mkdir(parents=True)
            dbc_file.write_bytes(b"test")

            with (
                patch("src.gui.spell_icons.PROJECT_ROOT", project_root),
                patch.dict(
                    os.environ,
                    {
                        "WOW_SPELL_ICON_DBC": "",
                        "WOW_EXTRACTED_CLIENT_ROOT": "",
                    },
                ),
            ):
                dbc, root = suggested_spell_icon_paths()

            self.assertEqual(dbc, str(dbc_file))
            self.assertEqual(root, str(project_root / "assets"))
            self.assertEqual(
                spell_icon_resource_directories(project_root / "assets"),
                (spellbook,),
            )

    def test_spell_icon_cache_finds_case_mismatched_blp_in_spellbook(self):
        feature = FEATURE_BY_ID["class.dk.bundle"]
        configuration = feature.default_configuration()
        profile = DatabaseProfile("测试")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dbc_file = root / "SpellIcon.dbc"
            icon_file = root / "Interface" / "Spellbook" / "spell_test.BLP"
            cache_root = root / "cache"
            icon_file.parent.mkdir(parents=True)
            strings = b"\0Interface\\Spellbook\\Spell_Test\0"
            dbc_file.write_bytes(
                struct.pack("<4s4I", b"WDBC", 1, 2, 8, len(strings))
                + struct.pack("<II", 136, 1)
                + strings
            )
            icon_file.write_bytes(b"spellbook-icon-source")

            cache = SpellIconCache(dbc_file, root, cache_root)
            reference = {
                "传染": SkillIconReference(
                    spell_id=50842, spell_icon_id=136, active_icon_id=0
                )
            }

            def convert(source, target):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())

            with patch.object(cache, "_convert_blp", side_effect=convert):
                result = cache.sync(profile, feature, configuration, reference)

            self.assertEqual(result.error, "")
            self.assertEqual(result.changed_skills, frozenset({"传染"}))
            self.assertEqual(
                result.paths["传染"].read_bytes(), b"spellbook-icon-source"
            )

    def test_spell_icon_dbc_lookup_and_persistent_difference_cache(self):
        feature = FEATURE_BY_ID["class.dk.bundle"]
        configuration = feature.default_configuration()
        profile = DatabaseProfile("测试")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dbc_file = root / "DBFilesClient" / "SpellIcon.dbc"
            icon_file = root / "Interface" / "Icons" / "Spell_Test.blp"
            cache_root = root / "cache"
            dbc_file.parent.mkdir(parents=True)
            icon_file.parent.mkdir(parents=True)
            strings = b"\0Interface\\Icons\\Spell_Test\0"
            dbc_file.write_bytes(
                struct.pack("<4s4I", b"WDBC", 1, 2, 8, len(strings))
                + struct.pack("<II", 136, 1)
                + strings
            )
            icon_file.write_bytes(b"first-icon-source")

            icon_map = load_spell_icon_dbc(dbc_file)
            self.assertEqual(icon_map, {136: "Interface\\Icons\\Spell_Test"})
            self.assertEqual(
                get_spell_icon_path(136, icon_map, root), icon_file
            )

            cache = SpellIconCache(dbc_file, root, cache_root)
            reference = {
                "传染": SkillIconReference(
                    spell_id=50842, spell_icon_id=136, active_icon_id=0
                )
            }

            def convert(source, target):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())

            with patch.object(cache, "_convert_blp", side_effect=convert) as converter:
                first = cache.sync(profile, feature, configuration, reference)
                self.assertEqual(first.changed_skills, frozenset({"传染"}))
                self.assertTrue(first.paths["传染"].is_file())
                self.assertEqual(converter.call_count, 1)

                unchanged = cache.sync(profile, feature, configuration, reference)
                self.assertEqual(unchanged.changed_skills, frozenset())
                self.assertEqual(converter.call_count, 1)

                unchanged.paths["传染"].write_bytes(b"damaged-cache")
                repaired = cache.sync(profile, feature, configuration, reference)
                self.assertEqual(repaired.changed_skills, frozenset({"传染"}))
                self.assertEqual(converter.call_count, 2)

                icon_file.write_bytes(b"updated-icon-source-with-new-size")
                updated = cache.sync(profile, feature, configuration, reference)
                self.assertEqual(updated.changed_skills, frozenset({"传染"}))
                self.assertEqual(converter.call_count, 3)

            reopened = SpellIconCache(dbc_file, root, cache_root)
            self.assertEqual(
                reopened.cached_paths(profile, feature, configuration), updated.paths
            )
            removed = reopened.sync(profile, feature, configuration, {})
            self.assertEqual(removed.changed_skills, frozenset({"传染"}))
            self.assertNotIn("传染", removed.paths)

    def test_saving_skill_configuration_keeps_loaded_run_state(self):
        feature = FEATURE_BY_ID["class.dk.bundle"]
        app = SimpleNamespace(
            settings=AppSettings(profiles=[DatabaseProfile("测试")]),
            latest={feature.id: object()},
        )
        config = feature.default_configuration()
        config["mod_gcd_time_skills"]["传染"]["value"] = "123"

        with patch("src.gui.app.save_settings") as persist:
            DbToolApp.save_feature_configuration(app, feature, config)

        persist.assert_called_once()
        self.assertIn(feature.id, app.latest)
        self.assertEqual(
            app.settings.feature_configs[feature.id]["mod_gcd_time_skills"]["传染"]["value"],
            "123",
        )









    def test_skill_details_use_conditions_and_display_name_fallback(self):
        group = SimpleNamespace(config_name="mod_gcd_time_skills", function="mod_gcd_time")
        feature = SimpleNamespace(
            configurable=True,
            module="tests.fake_skill_module",
            config_groups=(group,),
            default_configuration=lambda: {
                "mod_gcd_time_skills": {
                    "技能甲": {"enabled": True, "value": "250"},
                    "技能乙": {"enabled": True, "value": "0"},
                }
            },
        )
        module = SimpleNamespace(
            cond={
                "技能甲": "s.spellname4 = '技能甲' and s.StartRecoveryTime > 0",
                "技能乙": "s.spellname4 = '技能乙' and s.StartRecoveryTime > 0",
            }
        )

        def spell_row(spell_id, name, description, gcd, **extra):
            row = {
                "spell_id": spell_id,
                "spell_icon_id": 136 if spell_id == 1 else 0,
                "active_icon_id": 0,
                "spell_name": name,
                "skill_description": description,
                "proc_chance": 0,
                "proc_charges": 0,
                "duration_index": 0,
                "recovery_time": 0,
                "category_recovery_time": 0,
                "casting_time_index": 0,
                "start_recovery_category": 133 if gcd else 0,
                "start_recovery_time": gcd,
                "effect_misc_value_1": 0,
            }
            for slot in range(1, 4):
                row[f"effect_{slot}"] = 0
                row[f"effect_base_points_{slot}"] = 0
                row[f"effect_amplitude_{slot}"] = 0
                row[f"effect_apply_aura_{slot}"] = 0
                row[f"effect_trigger_spell_{slot}"] = 0
            row.update(extra)
            return row

        main_row = spell_row(
            1, "技能甲", "  第一行\n第二行  ", 1500,
            skill_match_0=1, skill_match_1=0,
        )
        fallback_rows = [
            spell_row(1, "技能甲", "技能甲描述", 1500),
            spell_row(2, "技能乙", "技能乙描述", 0),
        ]
        cursor = Mock()
        cursor.fetchall.side_effect = [[main_row], fallback_rows]
        connection = Mock()
        connection.cursor.return_value = cursor

        with patch(
            "src.gui.skill_descriptions.importlib.import_module", return_value=module
        ), patch(
            "src.gui.skill_descriptions.mysql.connector.connect", return_value=connection
        ) as connect:
            details = load_skill_details(DatabaseProfile("测试"), feature)

        self.assertEqual(
            details.descriptions,
            {"技能甲": "第一行 第二行", "技能乙": "技能乙描述"},
        )
        self.assertEqual(
            details.current_values,
            {
                ("mod_gcd_time_skills", "技能甲"): "1.5s",
                ("mod_gcd_time_skills", "技能乙"): "0ms",
            },
        )
        self.assertEqual(details.icons["技能甲"].spell_id, 1)
        self.assertEqual(details.icons["技能甲"].effective_icon_id, 136)
        connect.assert_called_once()
        connection.cursor.assert_called_once_with(dictionary=True)
        self.assertEqual(cursor.execute.call_count, 2)
        self.assertEqual(cursor.execute.call_args_list[1].args[1], ("技能甲", "技能乙"))
        cursor.close.assert_called_once()
        connection.close.assert_called_once()

    def test_custom_skill_details_use_saved_condition_and_return_current_value(self):
        group = SkillConfigGroup(
            "skills", "公共冷却时间", "mod_gcd_time", "毫秒"
        )
        feature = Feature(
            id="test.custom.bundle",
            title="测试职业",
            category="职业技能",
            description="",
            module="tests.fake_custom_skill_module",
            action_kind="spell_bundle",
            config_groups=(group,),
        )
        module = SimpleNamespace(
            cond={"代码技能": "s.ID=10"},
            skills={"代码技能": 0},
        )
        condition = "s.SpellName4='自定义技能' and s.ID=20"
        configuration = {
            "skills": {
                "代码技能": {"enabled": False, "value": "0"},
                "自定义技能": {"enabled": True, "value": "250"},
            },
            CUSTOM_SKILL_CONDITIONS_KEY: {"自定义技能": condition},
        }
        row = {
            "spell_id": 20,
            "spell_name": "自定义技能",
            "skill_description": "来自数据库的自定义技能描述",
            "effect_1": 0,
            "effect_2": 0,
            "effect_3": 0,
            "effect_base_points_1": 0,
            "effect_base_points_2": 0,
            "effect_base_points_3": 0,
            "effect_amplitude_1": 0,
            "effect_amplitude_2": 0,
            "effect_amplitude_3": 0,
            "effect_apply_aura_1": 0,
            "effect_apply_aura_2": 0,
            "effect_apply_aura_3": 0,
            "effect_trigger_spell_1": 0,
            "effect_trigger_spell_2": 0,
            "effect_trigger_spell_3": 0,
            "proc_chance": 0,
            "proc_charges": 0,
            "duration_index": 0,
            "recovery_time": 0,
            "category_recovery_time": 0,
            "casting_time_index": 0,
            "start_recovery_category": 133,
            "start_recovery_time": 250,
            "effect_misc_value_1": 0,
            "skill_match_0": 0,
            "skill_match_1": 1,
        }
        cursor = Mock()
        cursor.fetchall.side_effect = [[row], []]
        connection = Mock()
        connection.cursor.return_value = cursor

        with patch("importlib.import_module", return_value=module), patch(
            "src.gui.skill_descriptions.mysql.connector.connect",
            return_value=connection,
        ):
            details = load_skill_details(
                DatabaseProfile("测试"), feature, configuration
            )

        self.assertIn(condition, cursor.execute.call_args_list[0].args[0])
        self.assertEqual(
            details.descriptions["自定义技能"],
            "来自数据库的自定义技能描述",
        )
        self.assertEqual(details.current_values[("skills", "自定义技能")], "250ms")

    def test_custom_skill_condition_preview_is_read_only(self):
        cursor = Mock()
        cursor.fetchone.return_value = {"match_count": 2}
        cursor.fetchall.return_value = [
            {"spell_id": 20, "spell_name": "技能甲", "spell_rank": "等级 2"},
            {"spell_id": 10, "spell_name": "技能甲", "spell_rank": "等级 1"},
        ]
        connection = Mock()
        connection.cursor.return_value = cursor
        condition = "s.SpellName4='技能甲' and s.ID>0"

        with patch(
            "src.gui.skill_descriptions.mysql.connector.connect",
            return_value=connection,
        ):
            preview = preview_skill_condition(DatabaseProfile("测试"), condition)

        self.assertEqual(preview.count, 2)
        self.assertEqual(len(preview.rows), 2)
        sql = "\n".join(call.args[0] for call in cursor.execute.call_args_list)
        self.assertIn(f"WHERE ({condition})", sql)
        self.assertNotRegex(sql.lower(), r"\b(update|delete|insert|replace)\b")
        cursor.close.assert_called_once()
        connection.close.assert_called_once()



    def test_skill_details_map_each_modification_type_to_its_database_field(self):
        groups = (
            SimpleNamespace(config_name="damage", function="mod_dmg"),
            SimpleNamespace(config_name="chance", function="mod_trigger_chance"),
            SimpleNamespace(config_name="duration", function="mod_duration"),
            SimpleNamespace(config_name="cast", function="mod_cast_time"),
        )
        feature = SimpleNamespace(
            configurable=True,
            module="tests.fake_skill_module",
            config_groups=groups,
            default_configuration=lambda: {
                group.config_name: {"测试技能": {"enabled": True, "value": "1"}}
                for group in groups
            },
        )
        module = SimpleNamespace(cond={"测试技能": "s.ID = 10"})
        row = {
            "spell_id": 10,
            "spell_name": "测试技能",
            "skill_description": "测试描述",
            "effect_1": 2,
            "effect_2": 6,
            "effect_3": 0,
            "effect_base_points_1": 99,
            "effect_base_points_2": 4,
            "effect_base_points_3": 0,
            "effect_amplitude_1": 0,
            "effect_amplitude_2": 0,
            "effect_amplitude_3": 0,
            "effect_apply_aura_1": 0,
            "effect_apply_aura_2": 42,
            "effect_apply_aura_3": 0,
            "effect_trigger_spell_1": 0,
            "effect_trigger_spell_2": 123,
            "effect_trigger_spell_3": 0,
            "proc_chance": 25,
            "proc_charges": 3,
            "duration_index": 30,
            "recovery_time": 0,
            "category_recovery_time": 6000,
            "casting_time_index": 16,
            "start_recovery_category": 133,
            "start_recovery_time": 1500,
            "effect_misc_value_1": 0,
            "skill_match_0": 1,
        }
        cursor = Mock()
        cursor.fetchall.side_effect = [
            [row],
            [],
            [{"value_id": 30, "current_value": 1800000}],
            [{"value_id": 16, "current_value": 1500}],
        ]
        connection = Mock()
        connection.cursor.return_value = cursor

        with patch(
            "src.gui.skill_descriptions.importlib.import_module", return_value=module
        ), patch(
            "src.gui.skill_descriptions.mysql.connector.connect", return_value=connection
        ):
            details = load_skill_details(DatabaseProfile("测试"), feature)

        self.assertEqual(details.current_values[("damage", "测试技能")], "100")
        self.assertEqual(details.current_values[("chance", "测试技能")], "25%")
        self.assertEqual(details.current_values[("duration", "测试技能")], "1800s")
        self.assertEqual(details.current_values[("cast", "测试技能")], "1.5s")
        self.assertIn("spellduration", cursor.execute.call_args_list[2].args[0])
        self.assertIn("spellcasttimes", cursor.execute.call_args_list[3].args[0])


    def test_settings_round_trip_after_editing_existing_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            settings = AppSettings(
                profiles=[
                    DatabaseProfile("连接 A", "host-a"),
                    DatabaseProfile("连接 B", "host-b", 3307, "user-b", "pass-b", "db-b"),
                ],
                selected_profile=1,
            )
            settings.profiles[1] = DatabaseProfile(
                "连接 B（已修改）", "saved-host", 4406, "saved-user", "saved-pass", "saved-db"
            )

            save_settings(settings, path)
            loaded = load_settings(path)

            self.assertEqual(loaded.selected_profile, 1)
            self.assertEqual(loaded.profiles[1].name, "连接 B（已修改）")
            self.assertEqual(loaded.profiles[1].target_label, "saved-user@saved-host:4406/saved-db")

    def test_copy_item_does_not_mutate_reused_options(self):
        mysql = Mysql(auto_connect=False)
        mysql.get_column_names_and_cnt = Mock(return_value=["entry", "name", "value"])
        captured = []
        mysql._copy_item = lambda *args, **kwargs: (captured.append(args[3]) or ("SQL", ()))
        options = [["value", 2, "multi"]]
        mysql.copy_item(1, 2, options=options)
        mysql.copy_item(1, 3, options=options)
        self.assertEqual(options, [["value", 2, "multi"]])
        self.assertEqual(captured[0], [[2, 2, "multi"], [0, 2]])
        self.assertEqual(captured[1], [[2, 2, "multi"], [0, 3]])

    def test_runner_returns_failure_when_tracking_cannot_start(self):
        profile = DatabaseProfile("测试")
        feature = FEATURES[0]
        store = Mock()
        store.begin.side_effect = RuntimeError("no create permission")
        with patch("src.gui.runner.FeatureStateStore", return_value=store), patch("src.gui.runner.Mysql") as mysql:
            result = run_feature(profile, feature)
        self.assertFalse(result.ok)
        self.assertIn("功能尚未运行", result.error)
        mysql.assert_not_called()

class PyQtGuiMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])

    def setUp(self):
        settings_path = Path(__file__).resolve().parents[1] / ".db_tool_gui.json"
        self._real_settings_snapshot = (
            settings_path.read_bytes() if settings_path.exists() else None
        )

    def tearDown(self):
        # DbToolApp.closeEvent persists geometry. Keep test fixture windows from
        # ever writing their fake profiles into the developer's real settings.
        with patch("src.gui.app.save_settings"):
            for widget in list(QApplication.topLevelWidgets()):
                widget.close()
                widget.deleteLater()
            QApplication.processEvents()

        settings_path = Path(__file__).resolve().parents[1] / ".db_tool_gui.json"
        current = settings_path.read_bytes() if settings_path.exists() else None
        self.assertEqual(
            current,
            self._real_settings_snapshot,
            "PyQt GUI tests must not modify the project's real settings file",
        )

    def _skill_app(self, feature, *, icons=None, settings=None):
        settings = settings or AppSettings(profiles=[DatabaseProfile("测试")])
        icons = dict(icons or {})

        def request_details(_feature, callback, configuration=None):
            configuration = _feature.normalize_configuration(configuration)
            descriptions = {
                skill: f"{skill}描述"
                for group in _feature.config_groups
                for skill in configuration[group.config_name]
            }
            current_values = {
                (group.config_name, skill): f"{row + 1}ms"
                for group in _feature.config_groups
                for row, skill in enumerate(configuration[group.config_name])
            }
            callback(descriptions, current_values, "", SpellIconSyncResult(icons))

        return SimpleNamespace(
            settings=settings,
            profile=settings.profiles[settings.selected_profile],
            request_skill_details=request_details,
            cached_skill_icons=lambda _feature, _configuration: dict(icons),
            save_dialog_geometry=Mock(),
            save_feature_configuration=Mock(),
            show_skill_category_home=Mock(),
        )

    def test_profiles_dialog_has_visible_save_button_and_persists_edits(self):
        parent = QWidget()
        parent.settings = AppSettings(
            profiles=[DatabaseProfile("连接 A", "host-a")],
            window_geometry="1200x760",
            dialog_geometries={CUSTOM_SKILL_EDITOR_GEOMETRY_KEY: "800x700+70+80"},
            feature_configs={"feature": {"group": {}}},
            spell_icon_dbc_path="/tmp/SpellIcon.dbc",
            spell_icon_client_root="/tmp/wow-client",
        )
        parent.apply_settings = Mock()
        dialog = ProfilesDialog(parent)
        dialog.resize(dialog.minimumSize())
        dialog.show()
        QApplication.processEvents()

        buttons = {button.text(): button for button in dialog.findChildren(QPushButton)}
        self.assertIn("保存连接", buttons)
        self.assertTrue(buttons["保存连接"].isVisible())
        self.assertGreater(buttons["保存连接"].height(), 1)

        dialog.fields["name"].setText("连接 A（已修改）")
        dialog.fields["host"].setText("new-host")
        dialog.fields["port"].setText("4406")
        dialog.fields["database"].setText("new-db")
        dialog._save()

        updated = parent.apply_settings.call_args.args[0]
        self.assertEqual(updated.profiles[0].name, "连接 A（已修改）")
        self.assertEqual(updated.profiles[0].host, "new-host")
        self.assertEqual(updated.profiles[0].port, 4406)
        self.assertEqual(updated.profiles[0].database, "new-db")
        self.assertEqual(updated.window_geometry, "1200x760")
        self.assertEqual(updated.dialog_geometries, parent.settings.dialog_geometries)
        self.assertEqual(updated.feature_configs, parent.settings.feature_configs)

    def test_existing_profile_edit_is_committed_to_displayed_profile(self):
        parent = QWidget()
        parent.settings = AppSettings(
            profiles=[
                DatabaseProfile("连接 A", "host-a"),
                DatabaseProfile("连接 B", "host-b", 3307, "user-b", "pass-b", "db-b"),
            ],
            selected_profile=1,
        )
        parent.apply_settings = Mock()
        dialog = ProfilesDialog(parent)
        dialog.current = 0
        dialog.form_profile_index = 1
        values = {
            "name": "连接 B（已修改）",
            "host": "new-host",
            "port": "4406",
            "user": "new-user",
            "password": "new-pass",
            "database": "new-db",
            "auth_plugin": "mysql_native_password",
        }
        for key, value in values.items():
            dialog.fields[key].setText(value)

        dialog._commit_fields(validate=True)

        self.assertEqual(dialog.profiles[0].host, "host-a")
        self.assertEqual(dialog.profiles[1].name, "连接 B（已修改）")
        self.assertEqual(dialog.profiles[1].host, "new-host")
        self.assertEqual(dialog.profiles[1].port, 4406)
        self.assertEqual(dialog.profiles[1].database, "new-db")

    def test_custom_skill_dialog_geometry_templates_and_buttons(self):
        feature = FEATURE_BY_ID["class.dk.bundle"]
        settings = AppSettings(
            profiles=[DatabaseProfile("测试")],
            dialog_geometries={
                CUSTOM_SKILLS_DIALOG_GEOMETRY_KEY: "880x520+40+50",
                CUSTOM_SKILL_EDITOR_GEOMETRY_KEY: "740x700+60+70",
            },
        )
        view = SkillConfigView(self._skill_app(feature, settings=settings), feature)
        manager = CustomSkillsDialog(view)
        manager.show()
        QApplication.processEvents()
        self.assertEqual(manager.width(), 880)
        manager_buttons = {button.text(): button for button in manager.findChildren(QPushButton)}
        for label in ("新增技能", "编辑", "删除", "关闭"):
            self.assertTrue(manager_buttons[label].isVisible())

        editor = CustomSkillEditorDialog(manager)
        editor.show()
        QApplication.processEvents()
        self.assertEqual(editor.width(), 740)
        editor.skill_edit.setText("测试自定义技能")
        editor.template_box.setCurrentText("技能名称 + 单个 ID")
        editor._apply_condition_template()
        self.assertEqual(
            editor.condition_edit.toPlainText().strip(),
            "s.SpellName4='测试自定义技能' and s.ID=0",
        )
        self.assertIn("名称和 ID", editor.template_help.text())
        editor.resize(680, 680)
        editor.move(65, 75)
        editor.reject()
        view.app.save_dialog_geometry.assert_any_call(
            CUSTOM_SKILL_EDITOR_GEOMETRY_KEY, "680x680+65+75"
        )
        manager.resize(760, 480)
        manager.move(45, 55)
        manager.reject()
        view.app.save_dialog_geometry.assert_any_call(
            CUSTOM_SKILLS_DIALOG_GEOMETRY_KEY, "760x480+45+55"
        )

    def test_double_click_custom_skill_opens_populated_editor(self):
        feature = FEATURE_BY_ID["class.dk.bundle"]
        group = feature.config_groups[0]
        view = SkillConfigView(self._skill_app(feature), feature)
        view.upsert_custom_skill(
            None,
            None,
            group.config_name,
            "测试自定义技能",
            "s.SpellName4='测试自定义技能' and s.ID=12345",
            "250",
            True,
        )
        manager = CustomSkillsDialog(view)
        manager.table.selectRow(0)

        real_editor = CustomSkillEditorDialog(manager, group.config_name, "测试自定义技能")
        self.assertEqual(real_editor.skill_edit.text(), "测试自定义技能")
        self.assertEqual(real_editor.value_edit.text(), "250")
        self.assertEqual(
            real_editor.condition_edit.toPlainText(),
            "s.SpellName4='测试自定义技能' and s.ID=12345",
        )
        real_editor.close()

        with patch("src.gui.app.CustomSkillEditorDialog") as editor_class:
            editor_class.return_value.exec_.return_value = 0
            index = manager.table.model().index(0, 0)
            manager.table.doubleClicked.emit(index)
            QApplication.processEvents()
            editor_class.assert_called_once_with(
                manager, group.config_name, "测试自定义技能"
            )

    def test_scroll_frame_uses_native_qt_wheel_scrolling(self):
        frame = ScrollFrame()
        frame.resize(360, 240)
        for index in range(80):
            frame.add_widget(QLabel(f"滚动内容 {index}"))
        frame.show()
        QApplication.processEvents()
        bar = frame.verticalScrollBar()
        self.assertGreater(bar.maximum(), 0)
        before = bar.value()
        event = QWheelEvent(
            QPointF(10, 10),
            QPointF(10, 10),
            QPoint(0, 0),
            QPoint(0, -120),
            Qt.NoButton,
            Qt.NoModifier,
            Qt.ScrollUpdate,
            False,
        )
        QApplication.sendEvent(frame.viewport(), event)
        QApplication.processEvents()
        self.assertGreater(bar.value(), before)

    def test_class_skill_cards_each_have_configuration_button(self):
        settings = AppSettings(profiles=[DatabaseProfile("测试")])
        with patch("src.gui.app.load_settings", return_value=settings), patch.object(
            DbToolApp, "_refresh_worker"
        ), patch("src.gui.app.save_settings"):
            app = DbToolApp()
            app.resize(1040, 680)
            app._set_category("职业技能")
            app.show()
            QApplication.processEvents()
            titles = {label.text() for label in app.findChildren(QLabel)}
            self.assertTrue({"死亡骑士", "牧师", "盗贼", "萨满祭司"}.issubset(titles))
            buttons = [
                button for button in app.cards_frame.inner.findChildren(QPushButton)
                if button.text() == "配置技能" and button.isVisible()
            ]
            self.assertEqual(len(buttons), 4)

    def test_skill_configuration_headers_defaults_and_dynamic_details(self):
        feature = FEATURE_BY_ID["class.dk.bundle"]
        group = feature.config_groups[0]
        view = SkillConfigView(self._skill_app(feature), feature)
        view.resize(980, 680)
        view.show()
        QApplication.processEvents()
        table = view.tables[group.config_name]
        self.assertEqual(
            tuple(table.horizontalHeaderItem(column).text() for column in range(table.columnCount())),
            SkillConfigView.HEADERS,
        )
        self.assertLessEqual(table.columnWidth(2), 150)
        first_skill = next(iter(view.configuration[group.config_name]))
        key = (group.config_name, first_skill)
        self.assertEqual(
            view.value_widgets[key].text(),
            feature.default_configuration()[group.config_name][first_skill]["value"],
        )
        view.value_widgets[key].setText("3.25")
        self.assertEqual(view._collect()[group.config_name][first_skill]["value"], "3.25")
        self.assertEqual(view.current_items[key].text(), "1ms")
        self.assertEqual(view.description_items[first_skill][0].text(), f"{first_skill}描述")

    def test_skill_groups_keep_independent_scroll_positions(self):
        feature = FEATURE_BY_ID["class.dk.bundle"]
        view = SkillConfigView(self._skill_app(feature), feature)
        view.resize(780, 360)
        view.show()
        QApplication.processEvents()
        first = feature.config_groups[0]
        second = feature.config_groups[1]
        first_table = view.tables[first.config_name]
        self.assertGreater(first_table.verticalScrollBar().maximum(), 0)
        first_table.verticalScrollBar().setValue(first_table.verticalScrollBar().maximum())
        first_value = first_table.verticalScrollBar().value()
        view._activate_group(second.config_name)
        QApplication.processEvents()
        self.assertEqual(view.tables[second.config_name].verticalScrollBar().value(), 0)
        view._activate_group(first.config_name)
        QApplication.processEvents()
        self.assertEqual(first_table.verticalScrollBar().value(), first_value)

    def test_skill_editor_is_restored_after_visiting_history(self):
        feature = FEATURE_BY_ID["class.dk.bundle"]
        group = feature.config_groups[0]
        skill = next(iter(feature.default_configuration()[group.config_name]))
        settings = AppSettings(profiles=[DatabaseProfile("测试")])
        with patch("src.gui.app.load_settings", return_value=settings), patch.object(
            DbToolApp, "_refresh_worker"
        ), patch("src.gui.app.save_settings"), patch.object(
            FeatureStateStore, "history", return_value=[]
        ):
            app = DbToolApp()
            detail_app = self._skill_app(feature, settings=settings)
            app.request_skill_details = detail_app.request_skill_details
            app.cached_skill_icons = detail_app.cached_skill_icons
            app.show_skill_configuration(feature)
            original = app.current_skill_view
            original.value_widgets[(group.config_name, skill)].setText("123s")
            original._activate_group(feature.config_groups[1].config_name)
            app.show_history()
            QApplication.processEvents()
            app._set_category("职业技能")
            QApplication.processEvents()
            restored = app.current_skill_view
            self.assertIsNotNone(restored)
            self.assertEqual(restored.feature.id, feature.id)
            self.assertEqual(
                restored.value_widgets[(group.config_name, skill)].text(), "123s"
            )
            self.assertEqual(restored.active_group.config_name, feature.config_groups[1].config_name)

    def test_skill_columns_align_and_custom_skill_is_collected(self):
        feature = FEATURE_BY_ID["class.dk.bundle"]
        group = feature.config_groups[0]
        view = SkillConfigView(self._skill_app(feature), feature)
        table = view.tables[group.config_name]
        self.assertEqual(table.columnCount(), 6)
        self.assertEqual(table.horizontalHeader().count(), table.columnCount())
        view.upsert_custom_skill(
            None,
            None,
            group.config_name,
            "测试自定义技能",
            "s.SpellName4='测试自定义技能' and s.ID=12345",
            "250",
            True,
        )
        collected = view._collect()
        self.assertEqual(
            collected[group.config_name]["测试自定义技能"],
            {"enabled": True, "value": "250"},
        )
        self.assertEqual(
            collected[CUSTOM_SKILL_CONDITIONS_KEY]["测试自定义技能"],
            "s.SpellName4='测试自定义技能' and s.ID=12345",
        )
        key = (group.config_name, "测试自定义技能")
        self.assertEqual(view.current_items[key].text(), f"{len(view.configuration[group.config_name])}ms")
        self.assertEqual(view.description_items["测试自定义技能"][0].text(), "测试自定义技能描述")

    def test_cached_icons_appear_in_skill_and_custom_skill_views(self):
        feature = FEATURE_BY_ID["class.dk.bundle"]
        group = feature.config_groups[0]
        with tempfile.TemporaryDirectory() as directory:
            png = Path(directory) / "icon.png"
            Image.new("RGBA", (8, 8), (30, 120, 210, 255)).save(png)
            app = self._skill_app(feature, icons={"传染": png, "测试自定义技能": png})
            view = SkillConfigView(app, feature)
            row = list(view.configuration[group.config_name]).index("传染")
            self.assertFalse(view.tables[group.config_name].item(row, 1).icon().isNull())

            listener = Mock()
            view.add_icon_listener(listener)
            view._details_loaded({}, {}, "", SpellIconSyncResult(dict(view.icon_paths)))
            listener.assert_not_called()
            view._details_loaded(
                {}, {}, "", SpellIconSyncResult({"测试自定义技能": png}, frozenset({"传染"}))
            )
            self.assertTrue(view.tables[group.config_name].item(row, 1).icon().isNull())
            view._details_loaded(
                {}, {}, "", SpellIconSyncResult(
                    {"传染": png, "测试自定义技能": png}, frozenset({"传染"})
                )
            )
            self.assertEqual(listener.call_count, 2)

            view.upsert_custom_skill(
                None,
                None,
                group.config_name,
                "测试自定义技能",
                "s.SpellName4='测试自定义技能' and s.ID=12345",
                "250",
                True,
            )
            manager = CustomSkillsDialog(view)
            headers = tuple(
                manager.table.horizontalHeaderItem(column).text()
                for column in range(manager.table.columnCount())
            )
            self.assertEqual(
                headers,
                ("修改类型", "图标", "技能定义", "启用", "修改值", "查询条件"),
            )
            self.assertFalse(manager.table.item(0, 1).icon().isNull())

    def test_restore_defaults_does_not_reapply_stale_widget_values(self):
        feature = FEATURE_BY_ID["class.dk.bundle"]
        group = feature.config_groups[0]
        skill = next(iter(feature.default_configuration()[group.config_name]))
        view = SkillConfigView(self._skill_app(feature), feature)
        view.value_widgets[(group.config_name, skill)].setText("999")
        with patch("src.gui.app._confirm", return_value=True):
            view._reset_defaults()
        self.assertEqual(
            view.value_widgets[(group.config_name, skill)].text(),
            feature.default_configuration()[group.config_name][skill]["value"],
        )


if __name__ == "__main__":
    unittest.main()
