from __future__ import annotations

import copy
import importlib
import os
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from tkinter import ttk
from unittest.mock import Mock, patch

from src.core.mysql_core import Mysql
from src.customization.base import spell
from src.gui.app import DbToolApp, ProfilesDialog, SkillConfigView
from src.gui.config import AppSettings, DatabaseProfile, load_settings, save_settings
from src.gui.features import FEATURE_BY_ID, FEATURES
from src.gui.runner import run_feature


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


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
                for group in feature.config_groups:
                    values = getattr(module, group.config_name)
                    self.assertIsInstance(values, dict)
                    self.assertTrue(values)
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
            )
            save_settings(settings, path)
            loaded = load_settings(path)
            self.assertEqual(loaded.window_geometry, "1100x720")
            self.assertEqual(loaded.profiles[0].target_label, "wow@db.example:3307/world")
            self.assertEqual(loaded.profiles[0].connector_config()["password"], "secret")
            self.assertEqual(loaded.feature_configs, feature_config)

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

    @unittest.skipUnless(os.environ.get("DISPLAY"), "requires a graphical display")
    def test_profiles_dialog_action_buttons_visible_at_minimum_size(self):
        root = tk.Tk()
        root.settings = AppSettings(profiles=[DatabaseProfile("测试连接")])
        try:
            dialog = ProfilesDialog(root)
            dialog.geometry("720x520")
            dialog.update()

            buttons = {
                widget.cget("text"): widget
                for widget in descendants(dialog)
                if isinstance(widget, ttk.Button)
            }
            for label in ("测试当前连接", "保存连接", "取消"):
                button = buttons[label]
                top = button.winfo_rooty() - dialog.winfo_rooty()
                self.assertTrue(button.winfo_ismapped())
                self.assertGreater(button.winfo_height(), 1)
                self.assertLessEqual(top + button.winfo_height(), dialog.winfo_height())
        finally:
            root.destroy()

    @unittest.skipUnless(os.environ.get("DISPLAY"), "requires a graphical display")
    def test_class_skill_cards_each_have_configuration_button(self):
        settings = AppSettings(
            profiles=[DatabaseProfile("测试")],
            window_geometry="1040x680",
        )
        with patch("src.gui.app.load_settings", return_value=settings), patch(
            "src.gui.app.save_settings"
        ), patch.object(DbToolApp, "refresh_state", lambda self: None):
            app = DbToolApp()
            try:
                app.category = "职业技能"
                app.show_features()
                app.update()
                labels = [
                    widget.cget("text")
                    for widget in descendants(app.cards_frame.inner)
                    if isinstance(widget, tk.Label)
                ]
                buttons = [
                    widget
                    for widget in descendants(app.cards_frame.inner)
                    if isinstance(widget, ttk.Button) and widget.cget("text") == "配置技能"
                ]
                self.assertEqual(len(buttons), 4)
                for class_name in ("死亡骑士", "牧师", "盗贼", "萨满祭司"):
                    self.assertIn(class_name, labels)
                self.assertTrue(all(button.winfo_ismapped() for button in buttons))
            finally:
                for callback_id in app.tk.call("after", "info"):
                    app.after_cancel(callback_id)
                app.destroy()

    @unittest.skipUnless(os.environ.get("DISPLAY"), "requires a graphical display")
    def test_class_skill_configuration_view_at_minimum_main_size(self):
        root = tk.Tk()
        root.geometry("830x604")  # 1040x680 app minus sidebar/top bar
        main = tk.Frame(root)
        main.pack(fill="both", expand=True)
        app = SimpleNamespace(
            main=main,
            settings=AppSettings(profiles=[DatabaseProfile("测试")]),
            category="",
            show_features=Mock(),
            save_feature_configuration=Mock(),
        )
        try:
            feature = FEATURE_BY_ID["class.shaman.bundle"]
            view = SkillConfigView(app, feature)
            root.update()

            self.assertEqual(view.group_list.size(), len(feature.config_groups))
            last_bbox = view.group_list.bbox(view.group_list.size() - 1)
            self.assertIsNotNone(last_bbox)
            self.assertLessEqual(last_bbox[1] + last_bbox[3], view.group_list.winfo_height())

            buttons = {
                widget.cget("text"): widget
                for widget in descendants(view)
                if isinstance(widget, ttk.Button)
            }
            for label in ("← 返回职业技能", "恢复代码默认值", "保存配置"):
                self.assertTrue(buttons[label].winfo_ismapped())
                right = buttons[label].winfo_rootx() - root.winfo_rootx() + buttons[label].winfo_width()
                self.assertLessEqual(right, root.winfo_width())

            first_group = feature.config_groups[0]
            entries = [widget for widget in descendants(view) if isinstance(widget, ttk.Entry)]
            checks = [widget for widget in descendants(view) if isinstance(widget, tk.Checkbutton)]
            self.assertEqual(len(entries), len(view.configuration[first_group.config_name]))
            self.assertEqual(len(checks), len(view.configuration[first_group.config_name]))

            view.group_list.selection_clear(0, "end")
            view.group_list.selection_set(view.group_list.size() - 1)
            view._group_selected()
            root.update()
            last_group = feature.config_groups[-1]
            entries = [widget for widget in descendants(view) if isinstance(widget, ttk.Entry)]
            checks = [widget for widget in descendants(view) if isinstance(widget, tk.Checkbutton)]
            self.assertEqual(len(entries), len(view.configuration[last_group.config_name]))
            self.assertEqual(len(checks), len(view.configuration[last_group.config_name]))
        finally:
            root.destroy()

    def test_existing_profile_edit_is_committed_to_displayed_profile(self):
        dialog = ProfilesDialog.__new__(ProfilesDialog)
        dialog.profiles = [
            DatabaseProfile("连接 A", "host-a", 3306, "user-a", "pass-a", "db-a"),
            DatabaseProfile("连接 B", "host-b", 3307, "user-b", "pass-b", "db-b"),
        ]
        # Simulate a delayed Listbox event changing `current` while the form is
        # still displaying profile B. The edit must remain attached to B.
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
        dialog.vars = {key: Mock(get=Mock(return_value=value)) for key, value in values.items()}

        dialog._commit_fields(validate=True)

        self.assertEqual(dialog.profiles[0].host, "host-a")
        self.assertEqual(dialog.profiles[1].name, "连接 B（已修改）")
        self.assertEqual(dialog.profiles[1].host, "new-host")
        self.assertEqual(dialog.profiles[1].port, 4406)
        self.assertEqual(dialog.profiles[1].database, "new-db")

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


if __name__ == "__main__":
    unittest.main()
