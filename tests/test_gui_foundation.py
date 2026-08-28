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
from src.gui.state import FeatureStateStore


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

    def test_profile_save_keeps_dialog_layout_settings(self):
        original_settings = AppSettings(
            profiles=[DatabaseProfile("旧连接")],
            window_geometry="1200x760",
            feature_configs={"feature": {"group": {}}},
            dialog_geometries={
                CUSTOM_SKILL_EDITOR_GEOMETRY_KEY: "800x700+70+80"
            },
        )
        app = SimpleNamespace(
            settings=original_settings, apply_settings=Mock()
        )
        dialog = ProfilesDialog.__new__(ProfilesDialog)
        dialog.app = app
        dialog.profiles = [DatabaseProfile("新连接")]
        dialog.form_profile_index = 0
        dialog._commit_fields = Mock()
        dialog.destroy = Mock()

        dialog._save()

        updated = app.apply_settings.call_args.args[0]
        self.assertEqual(updated.window_geometry, "1200x760")
        self.assertEqual(updated.feature_configs, original_settings.feature_configs)
        self.assertEqual(
            updated.dialog_geometries, original_settings.dialog_geometries
        )
        dialog.destroy.assert_called_once()

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
    def test_custom_skill_dialog_buttons_stay_visible_and_layout_is_saved(self):
        root = tk.Tk()
        feature = FEATURE_BY_ID["class.dk.bundle"]
        save_geometry = Mock()
        app = SimpleNamespace(
            settings=AppSettings(
                profiles=[DatabaseProfile("测试")],
                dialog_geometries={
                    CUSTOM_SKILLS_DIALOG_GEOMETRY_KEY: "880x520+40+50",
                    CUSTOM_SKILL_EDITOR_GEOMETRY_KEY: "740x700+60+70",
                },
            ),
            profile=DatabaseProfile("测试"),
            save_dialog_geometry=save_geometry,
        )
        view = tk.Frame(root)
        view.app = app
        view.feature = feature
        view.active_group = feature.config_groups[0]
        view.configuration = feature.default_configuration()
        view.custom_conditions = {}
        view.custom_skill_rows = Mock(return_value=[])
        view.upsert_custom_skill = Mock()
        view.remove_custom_skill = Mock()
        view.pack()
        manager = None
        editor = None
        try:
            manager = CustomSkillsDialog(view)
            manager.update()
            self.assertEqual(manager.winfo_width(), 880)
            manager.geometry("760x480+45+55")
            manager.update()

            manager_buttons = {
                widget.cget("text"): widget
                for widget in descendants(manager)
                if isinstance(widget, ttk.Button)
            }
            for label in ("新增技能", "编辑", "删除", "关闭"):
                button = manager_buttons[label]
                bottom = button.winfo_rooty() - manager.winfo_rooty() + button.winfo_height()
                self.assertTrue(button.winfo_ismapped())
                self.assertLessEqual(bottom, manager.winfo_height())

            editor = CustomSkillEditorDialog(manager)
            editor.update()
            self.assertEqual(editor.winfo_width(), 740)
            editor.skill_var.set("测试自定义技能")
            editor.template_var.set("技能名称 + 单个 ID")
            editor._template_selected()
            editor._apply_condition_template()
            self.assertEqual(
                editor.condition_text.get("1.0", "end").strip(),
                "s.SpellName4='测试自定义技能' and s.ID=0",
            )
            self.assertIn("名称和 ID", editor.template_help_var.get())
            editor.geometry("680x680+65+75")
            editor.preview_var.set("\n".join(f"查询结果 {index}" for index in range(30)))
            editor._render_preview()
            editor.update()

            editor_buttons = {
                widget.cget("text"): widget
                for widget in descendants(editor)
                if isinstance(widget, ttk.Button)
            }
            for label in ("测试查询", "保存并查询", "取消"):
                button = editor_buttons[label]
                bottom = button.winfo_rooty() - editor.winfo_rooty() + button.winfo_height()
                self.assertTrue(button.winfo_ismapped())
                self.assertLessEqual(bottom, editor.winfo_height())

            editor._close()
            editor = None
            manager._close()
            manager = None
            calls = save_geometry.call_args_list
            self.assertEqual(calls[0].args[0], CUSTOM_SKILL_EDITOR_GEOMETRY_KEY)
            self.assertTrue(calls[0].args[1].startswith("680x680"))
            self.assertEqual(calls[1].args[0], CUSTOM_SKILLS_DIALOG_GEOMETRY_KEY)
            self.assertTrue(calls[1].args[1].startswith("760x480"))
        finally:
            if editor is not None and editor.winfo_exists():
                editor.destroy()
            if manager is not None and manager.winfo_exists():
                manager.destroy()
            root.destroy()

    @unittest.skipUnless(os.environ.get("DISPLAY"), "requires a graphical display")
    def test_scroll_frame_accepts_linux_mouse_wheel_buttons_over_content(self):
        root = tk.Tk()
        root.geometry("360x240+20+20")
        frame = ScrollFrame(root)
        frame.pack(fill="both", expand=True)
        labels = []
        try:
            for index in range(80):
                label = tk.Label(frame.inner, text=f"滚动内容 {index}")
                label.pack(anchor="w", pady=2)
                labels.append(label)
            root.update()
            before = frame.canvas.yview()[0]
            # Use a currently visible child; off-screen widgets do not have a
            # screen coordinate that winfo_containing can resolve.
            target = labels[2]
            event = SimpleNamespace(
                num=5, delta=0,
                x_root=target.winfo_rootx() + 2,
                y_root=target.winfo_rooty() + 2,
            )
            self.assertEqual(frame._mousewheel(event), "break")
            root.update()
            self.assertGreater(frame.canvas.yview()[0], before)

            event.num = 4
            self.assertEqual(frame._mousewheel(event), "break")
            root.update()
            self.assertLessEqual(frame.canvas.yview()[0], before)
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
        feature = FEATURE_BY_ID["class.shaman.bundle"]
        descriptions = {
            skill: f"{skill}的数据库技能描述"
            for skill in skill_names(feature)
        }
        current_values = {
            (group_name, skill): "1.5s"
            for group_name, skills in feature.default_configuration().items()
            for skill in skills
        }
        app = SimpleNamespace(
            main=main,
            settings=AppSettings(profiles=[DatabaseProfile("测试")]),
            profile=DatabaseProfile("测试"),
            category="",
            show_features=Mock(),
            save_feature_configuration=Mock(),
            request_skill_details=lambda _feature, callback: callback(
                descriptions, current_values, ""
            ),
        )
        try:
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
            for label in (
                "← 返回职业技能",
                "管理自定义技能",
                "恢复代码默认值",
                "保存配置",
            ):
                self.assertTrue(buttons[label].winfo_ismapped())
                self.assertGreater(buttons[label].winfo_width(), 70)
                right = buttons[label].winfo_rootx() - root.winfo_rootx() + buttons[label].winfo_width()
                self.assertLessEqual(right, root.winfo_width())

            first_group = feature.config_groups[0]
            entries = [widget for widget in descendants(view) if isinstance(widget, ttk.Entry)]
            checks = [widget for widget in descendants(view) if isinstance(widget, tk.Checkbutton)]
            self.assertEqual(len(entries), len(view.configuration[first_group.config_name]))
            self.assertEqual(len(checks), len(view.configuration[first_group.config_name]))
            self.assertTrue(all(entry.winfo_height() > 1 for entry in entries))

            labels = [widget for widget in descendants(view) if isinstance(widget, tk.Label)]
            self.assertTrue(any(label.cget("text") == "当前值" for label in labels))
            self.assertTrue(any(label.cget("text") == "技能描述" for label in labels))
            skill_labels = [label for label in labels if label.cget("text") in descriptions]
            self.assertTrue(skill_labels)
            self.assertTrue(all(int(label.cget("width")) <= 10 for label in skill_labels))

            first_skill = next(iter(view.configuration[first_group.config_name]))
            first_key = (first_group.config_name, first_skill)
            self.assertEqual(view.current_value_vars[first_key].get(), current_values[first_key])
            self.assertEqual(view.description_vars[first_skill].get(), descriptions[first_skill])
            current_label = next(
                label
                for label in labels
                if label.cget("text") == current_values[first_key]
                and int(label.cget("width")) == 17
            )
            current_right = (
                current_label.winfo_rootx() - root.winfo_rootx()
                + current_label.winfo_width()
            )
            self.assertTrue(current_label.winfo_ismapped())
            self.assertLessEqual(current_right, root.winfo_width())
            description_label = next(
                label
                for label in labels
                if label.cget("text") == descriptions[first_skill]
            )
            description_right = (
                description_label.winfo_rootx() - root.winfo_rootx()
                + description_label.winfo_width()
            )
            self.assertTrue(description_label.winfo_ismapped())
            self.assertLessEqual(description_right, root.winfo_width())
            first_entry = entries[0]
            self.assertEqual(
                first_entry.get(),
                view.configuration[first_group.config_name][first_skill]["value"],
            )
            first_entry.delete(0, "end")
            first_entry.insert(0, "3.25")
            self.assertEqual(view.value_vars[(first_group.config_name, first_skill)].get(), "3.25")

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

    @unittest.skipUnless(os.environ.get("DISPLAY"), "requires a graphical display")
    def test_skill_groups_keep_independent_scroll_positions(self):
        root = tk.Tk()
        root.geometry("830x604")
        main = tk.Frame(root)
        main.pack(fill="both", expand=True)
        feature = FEATURE_BY_ID["class.dk.bundle"]
        app = SimpleNamespace(
            main=main,
            settings=AppSettings(profiles=[DatabaseProfile("测试")]),
            profile=DatabaseProfile("测试"),
            request_skill_details=lambda _feature, callback: callback({}, {}, ""),
        )
        try:
            view = SkillConfigView(app, feature)
            root.update()

            view.detail.canvas.yview_moveto(1.0)
            root.update()
            gcd_position = view.detail.canvas.yview()[0]
            self.assertGreater(gcd_position, 0.0)

            view.group_list.selection_clear(0, "end")
            view.group_list.selection_set(1)
            view._group_selected()
            root.update()
            self.assertAlmostEqual(view.detail.canvas.yview()[0], 0.0, places=3)

            view.group_list.selection_clear(0, "end")
            view.group_list.selection_set(0)
            view._group_selected()
            root.update()
            self.assertAlmostEqual(
                view.detail.canvas.yview()[0], gcd_position, delta=0.02
            )
        finally:
            root.destroy()

    @unittest.skipUnless(os.environ.get("DISPLAY"), "requires a graphical display")
    def test_class_skill_editor_is_restored_after_visiting_history(self):
        settings = AppSettings(
            profiles=[DatabaseProfile("测试")],
            window_geometry="1040x680",
        )
        feature = FEATURE_BY_ID["class.dk.bundle"]
        with patch("src.gui.app.load_settings", return_value=settings), patch(
            "src.gui.app.save_settings"
        ), patch.object(DbToolApp, "refresh_state", lambda self: None), patch.object(
            DbToolApp,
            "request_skill_details",
            lambda self, _feature, callback: callback({}, {}, ""),
        ), patch.object(FeatureStateStore, "history", return_value=[]):
            app = DbToolApp()
            try:
                app.show_skill_configuration(feature)
                app.update()
                original_view = app.current_skill_view
                self.assertIsNotNone(original_view)

                group = feature.config_groups[1]
                skill = next(iter(original_view.configuration[group.config_name]))
                original_view.value_vars[(group.config_name, skill)].set("123s")
                original_view.group_list.selection_clear(0, "end")
                original_view.group_list.selection_set(1)
                original_view._group_selected()
                app.update()

                app.show_history()
                app.update()
                self.assertIsNone(app.current_skill_view)

                app._set_category("职业技能")
                app.update()
                restored_view = app.current_skill_view
                self.assertIsNotNone(restored_view)
                self.assertEqual(restored_view.feature.id, feature.id)
                self.assertEqual(restored_view.active_group.config_name, group.config_name)
                self.assertEqual(
                    restored_view.value_vars[(group.config_name, skill)].get(),
                    "123s",
                )

                restored_view._back()
                app.update()
                self.assertIsNone(app.active_skill_feature_id)
                self.assertIsNone(app.current_skill_view)
                self.assertTrue(app.cards_frame.winfo_exists())
            finally:
                for callback_id in app.tk.call("after", "info"):
                    app.after_cancel(callback_id)
                app.destroy()

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

    @unittest.skipUnless(os.environ.get("DISPLAY"), "requires a graphical display")
    def test_skill_columns_align_and_gui_custom_skill_is_collected(self):
        root = tk.Tk()
        root.geometry("830x604")
        main = tk.Frame(root)
        main.pack(fill="both", expand=True)
        feature = FEATURE_BY_ID["class.dk.bundle"]
        requests = []

        def request_details(_feature, callback, configuration):
            requests.append(copy.deepcopy(configuration))
            descriptions = {
                skill: f"{skill}描述"
                for group in feature.config_groups
                for skill in configuration[group.config_name]
            }
            current_values = {
                (group.config_name, skill): "250ms"
                for group in feature.config_groups
                for skill in configuration[group.config_name]
            }
            callback(descriptions, current_values, "")

        app = SimpleNamespace(
            main=main,
            settings=AppSettings(profiles=[DatabaseProfile("测试")]),
            profile=DatabaseProfile("测试"),
            request_skill_details=request_details,
        )
        try:
            view = SkillConfigView(app, feature)
            root.update()
            group = feature.config_groups[0]
            first_skill = next(iter(view.configuration[group.config_name]))
            first_widgets = view.row_column_widgets[(group.config_name, first_skill)]
            for column in (1, 2, 3, 4):
                self.assertAlmostEqual(
                    view.column_header_widgets[column].winfo_rootx(),
                    first_widgets[column].winfo_rootx(),
                    delta=1,
                )

            condition = "s.SpellName4='测试自定义技能' and s.ID=12345"
            view.upsert_custom_skill(
                None,
                None,
                group.config_name,
                "测试自定义技能",
                condition,
                "250",
                True,
            )
            root.update()
            collected = view._collect()
            self.assertEqual(
                collected[CUSTOM_SKILL_CONDITIONS_KEY],
                {"测试自定义技能": condition},
            )
            self.assertEqual(
                collected[group.config_name]["测试自定义技能"],
                {"enabled": True, "value": "250"},
            )
            self.assertEqual(
                view.current_value_vars[(group.config_name, "测试自定义技能")].get(),
                "250ms",
            )
            self.assertEqual(
                view.description_vars["测试自定义技能"].get(),
                "测试自定义技能描述",
            )
            self.assertIn("测试自定义技能", requests[-1][group.config_name])

            view.remove_custom_skill(group.config_name, "测试自定义技能")
            self.assertNotIn(
                "测试自定义技能", view._collect()[group.config_name]
            )
            self.assertEqual(
                view._collect()[CUSTOM_SKILL_CONDITIONS_KEY], {}
            )
            root.update()
        finally:
            root.destroy()

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
