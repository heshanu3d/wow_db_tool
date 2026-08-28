from __future__ import annotations

import copy
import importlib
import inspect
import re
import sys
import threading
import traceback
from dataclasses import replace
from pathlib import Path
from typing import Callable

from PyQt5.QtCore import QObject, QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QIcon, QPixmap
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .config import AppSettings, DatabaseProfile, load_settings, save_settings
from .features import (
    CATEGORIES,
    CUSTOM_SKILL_CONDITIONS_KEY,
    FEATURES,
    SKILL_CONDITION_TEMPLATE_BY_TITLE,
    SKILL_CONDITION_TEMPLATES,
    Feature,
    validate_skill_condition,
)
from .runner import RunResult, run_feature
from .skill_descriptions import load_skill_details, preview_skill_condition
from .spell_icons import (
    SpellIconCache,
    SpellIconSyncResult,
    load_spell_icon_dbc,
    spell_icon_resource_directories,
    suggested_spell_icon_paths,
)
from .state import FeatureRun, FeatureStateStore

COLORS = {
    "ink": "#162033",
    "muted": "#667085",
    "paper": "#F4F7FA",
    "surface": "#FFFFFF",
    "line": "#D7DEE8",
    "navy": "#162C46",
    "navy_2": "#234564",
    "gold": "#C68A2B",
    "gold_soft": "#F5E7CB",
    "teal": "#187B78",
    "teal_soft": "#DDF1EE",
    "red": "#B84444",
    "red_soft": "#F8E5E5",
    "blue_soft": "#E3EDF7",
    "slate_soft": "#E9EDF2",
}

CUSTOM_SKILLS_DIALOG_GEOMETRY_KEY = "custom_skills_manager"
CUSTOM_SKILL_EDITOR_GEOMETRY_KEY = "custom_skill_editor"

STATUS_STYLE = {
    "none": ("未应用", COLORS["muted"], COLORS["slate_soft"]),
    "applied": ("已应用", COLORS["teal"], COLORS["teal_soft"]),
    "marked": ("已标记", COLORS["teal"], COLORS["teal_soft"]),
    "updated": ("代码/配置有更新", "#946314", COLORS["gold_soft"]),
    "failed": ("执行失败", COLORS["red"], COLORS["red_soft"]),
    "running": ("执行中", COLORS["navy_2"], COLORS["blue_soft"]),
}

_GEOMETRY_RE = re.compile(
    r"^\s*(?P<w>\d+)x(?P<h>\d+)(?P<x>[+-]\d+)?(?P<y>[+-]\d+)?\s*$"
)


def _apply_saved_geometry(widget: QWidget, geometry: str, default: str) -> None:
    """Restore the existing Tk-style geometry strings with PyQt."""
    match = _GEOMETRY_RE.match(geometry or "") or _GEOMETRY_RE.match(default)
    if match is None:
        return
    width, height = int(match.group("w")), int(match.group("h"))
    widget.resize(width, height)
    if match.group("x") is not None and match.group("y") is not None:
        widget.move(int(match.group("x")), int(match.group("y")))


def _geometry_string(widget: QWidget) -> str:
    return f"{widget.width()}x{widget.height()}+{widget.x()}+{widget.y()}"


def _load_qpixmap(path: str | Path, size: int = 34) -> QPixmap | None:
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return None
    return pixmap.scaled(
        size,
        size,
        Qt.KeepAspectRatio,
        Qt.SmoothTransformation,
    )




def _restore_scroll_value(table: QTableWidget, value: int) -> None:
    """Restore a table scroll position after Qt has calculated its range."""
    try:
        table.verticalScrollBar().setValue(value)
    except RuntimeError:
        # The view may have been replaced before the queued callback runs.
        pass

def _message_error(parent: QWidget, title: str, text: str) -> None:
    QMessageBox.critical(parent, title, text)


def _message_info(parent: QWidget, title: str, text: str) -> None:
    QMessageBox.information(parent, title, text)


def _confirm(parent: QWidget, title: str, text: str, warning: bool = False) -> bool:
    icon = QMessageBox.Warning if warning else QMessageBox.Question
    box = QMessageBox(icon, title, text, QMessageBox.Yes | QMessageBox.No, parent)
    box.setDefaultButton(QMessageBox.No)
    return box.exec_() == QMessageBox.Yes


class ScrollFrame(QScrollArea):
    """Compatibility name for the old scroll container, now backed by Qt."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.inner = QWidget()
        self.layout = QVBoxLayout(self.inner)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(10)
        self.layout.addStretch(1)
        self.setWidget(self.inner)

    def clear(self) -> None:
        while self.layout.count() > 1:
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def add_widget(self, widget: QWidget) -> None:
        self.layout.insertWidget(self.layout.count() - 1, widget)


class _WorkerSignals(QObject):
    state_ready = pyqtSignal(object, str)
    run_progress = pyqtSignal(object)
    run_finished = pyqtSignal(object)
    skill_details_ready = pyqtSignal(object, object, object, str, object)


class ProfilesDialog(QDialog):
    def __init__(self, master: "DbToolApp"):
        super().__init__(master)
        self.app = master
        self.setWindowTitle("数据库连接配置")
        self.setMinimumSize(720, 520)
        self.resize(780, 560)
        self.setModal(True)
        self.profiles = [replace(profile) for profile in master.settings.profiles]
        self.current = min(
            max(0, master.settings.selected_profile), len(self.profiles) - 1
        )
        self.form_profile_index = self.current
        self.fields: dict[str, QLineEdit] = {}
        self._build()
        self._refresh_list()
        self.listbox.setCurrentRow(self.current)
        self._load_current()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 16)
        title = QLabel("数据库目标")
        title.setObjectName("dialogTitle")
        subtitle = QLabel("执行状态会记录在所选数据库中")
        subtitle.setObjectName("muted")
        root.addWidget(title)
        root.addWidget(subtitle)

        splitter = QSplitter(Qt.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.listbox = QListWidget()
        self.listbox.currentRowChanged.connect(self._select_profile)
        left_layout.addWidget(self.listbox)
        list_actions = QHBoxLayout()
        add_button = QPushButton("新增")
        delete_button = QPushButton("删除")
        add_button.clicked.connect(self._add)
        delete_button.clicked.connect(self._delete)
        list_actions.addWidget(add_button)
        list_actions.addWidget(delete_button)
        left_layout.addLayout(list_actions)

        form_box = QGroupBox("连接信息")
        form = QFormLayout(form_box)
        specs = (
            ("连接名称", "name", False),
            ("主机地址", "host", False),
            ("端口", "port", False),
            ("用户名", "user", False),
            ("密码", "password", True),
            ("数据库", "database", False),
            ("认证插件", "auth_plugin", False),
        )
        for label, key, secret in specs:
            edit = QLineEdit()
            if secret:
                edit.setEchoMode(QLineEdit.Password)
            self.fields[key] = edit
            form.addRow(label, edit)
        splitter.addWidget(left)
        splitter.addWidget(form_box)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([210, 520])
        root.addWidget(splitter, 1)

        actions = QHBoxLayout()
        test_button = QPushButton("测试当前连接")
        cancel_button = QPushButton("取消")
        save_button = QPushButton("保存连接")
        save_button.setObjectName("primaryButton")
        test_button.clicked.connect(self._test)
        cancel_button.clicked.connect(self.reject)
        save_button.clicked.connect(self._save)
        actions.addWidget(test_button)
        actions.addStretch(1)
        actions.addWidget(cancel_button)
        actions.addWidget(save_button)
        root.addLayout(actions)

    def _refresh_list(self) -> None:
        row = max(0, min(self.form_profile_index, len(self.profiles) - 1))
        self.listbox.blockSignals(True)
        self.listbox.clear()
        self.listbox.addItems([profile.name for profile in self.profiles])
        self.listbox.setCurrentRow(row)
        self.listbox.blockSignals(False)

    def _load_current(self) -> None:
        if not self.profiles:
            return
        profile = self.profiles[self.form_profile_index]
        values = {
            "name": profile.name,
            "host": profile.host,
            "port": str(profile.port),
            "user": profile.user,
            "password": profile.password,
            "database": profile.database,
            "auth_plugin": profile.auth_plugin,
        }
        for key, value in values.items():
            self.fields[key].setText(value)

    def _commit_fields(self, validate: bool = False) -> None:
        if not self.profiles:
            return
        try:
            port = int(self.fields["port"].text().strip() or 3306)
        except ValueError:
            if validate:
                raise ValueError("端口必须是 1 到 65535 之间的整数。")
            return
        if not 1 <= port <= 65535:
            if validate:
                raise ValueError("端口必须是 1 到 65535 之间的整数。")
            return
        profile = self.profiles[self.form_profile_index]
        profile.name = self.fields["name"].text().strip() or "未命名连接"
        profile.host = self.fields["host"].text().strip()
        profile.port = port
        profile.user = self.fields["user"].text().strip()
        profile.password = self.fields["password"].text()
        profile.database = self.fields["database"].text().strip()
        profile.auth_plugin = self.fields["auth_plugin"].text().strip()

    def _select_profile(self, row: int) -> None:
        if row < 0 or row >= len(self.profiles) or row == self.form_profile_index:
            return
        self._commit_fields(validate=False)
        self.form_profile_index = row
        self.current = row
        self._load_current()

    def _add(self) -> None:
        self._commit_fields(validate=False)
        self.profiles.append(DatabaseProfile(name=f"新连接 {len(self.profiles) + 1}"))
        self.form_profile_index = len(self.profiles) - 1
        self.current = self.form_profile_index
        self._refresh_list()
        self._load_current()
        self.fields["name"].setFocus()
        self.fields["name"].selectAll()

    def _delete(self) -> None:
        if len(self.profiles) <= 1:
            _message_info(self, "不能删除", "至少保留一个数据库连接。")
            return
        row = self.listbox.currentRow()
        if row < 0:
            return
        del self.profiles[row]
        self.form_profile_index = min(row, len(self.profiles) - 1)
        self.current = self.form_profile_index
        self._refresh_list()
        self._load_current()

    def _test(self) -> None:
        try:
            self._commit_fields(validate=True)
            profile = self.profiles[self.form_profile_index]
            QApplication.setOverrideCursor(Qt.WaitCursor)
            version = FeatureStateStore(profile).test_connection()
            _message_info(
                self,
                "连接成功",
                f"{profile.target_label}\nMySQL {version}",
            )
        except Exception as exc:
            _message_error(self, "连接失败", str(exc))
        finally:
            QApplication.restoreOverrideCursor()

    def _save(self) -> None:
        try:
            self._commit_fields(validate=True)
            updated = AppSettings(
                profiles=[replace(profile) for profile in self.profiles],
                selected_profile=self.form_profile_index,
                window_geometry=self.app.settings.window_geometry,
                dialog_geometries=copy.deepcopy(
                    self.app.settings.dialog_geometries
                ),
                feature_configs=copy.deepcopy(self.app.settings.feature_configs),
                spell_icon_dbc_path=self.app.settings.spell_icon_dbc_path,
                spell_icon_client_root=self.app.settings.spell_icon_client_root,
            )
            self.app.apply_settings(updated)
        except (OSError, ValueError, TypeError) as exc:
            _message_error(self, "保存连接失败", str(exc))
            return
        self.accept()


class IconResourcesDialog(QDialog):
    def __init__(self, app: "DbToolApp", parent: QWidget | None = None):
        super().__init__(parent or app)
        self.app = app
        self.setWindowTitle("技能图标资源")
        self.setMinimumSize(680, 300)
        self.resize(760, 330)
        self.setModal(True)
        suggested_dbc, suggested_root = suggested_spell_icon_paths()
        self.dbc_edit = QLineEdit(app.settings.spell_icon_dbc_path or suggested_dbc)
        self.root_edit = QLineEdit(
            app.settings.spell_icon_client_root or suggested_root
        )
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        title = QLabel("技能图标资源")
        title.setObjectName("dialogTitle")
        description = QLabel(
            "需要 SpellIcon.dbc，以及 Interface/Icons/*.blp 或 "
            "Interface/Spellbook/*.blp。界面优先显示 PNG 缓存，后台再同步数据库与资源差异。"
        )
        description.setWordWrap(True)
        description.setObjectName("muted")
        root.addWidget(title)
        root.addWidget(description)

        form = QFormLayout()
        dbc_row = QWidget()
        dbc_layout = QHBoxLayout(dbc_row)
        dbc_layout.setContentsMargins(0, 0, 0, 0)
        dbc_layout.addWidget(self.dbc_edit)
        dbc_button = QPushButton("浏览…")
        dbc_button.clicked.connect(self._choose_dbc)
        dbc_layout.addWidget(dbc_button)
        form.addRow("SpellIcon.dbc", dbc_row)

        root_row = QWidget()
        root_layout = QHBoxLayout(root_row)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self.root_edit)
        root_button = QPushButton("浏览…")
        root_button.clicked.connect(self._choose_root)
        root_layout.addWidget(root_button)
        form.addRow("客户端解压根目录", root_row)
        root.addLayout(form)

        note = QLabel(
            "根目录下应存在 Interface/Icons 或 Interface/Spellbook；也可以直接选择 "
            "Icons/Spellbook 目录。清空两个路径可停用同步，现有缓存仍会显示。"
        )
        note.setObjectName("muted")
        note.setWordWrap(True)
        root.addWidget(note)
        root.addStretch(1)

        buttons = QDialogButtonBox()
        cancel = buttons.addButton("取消", QDialogButtonBox.RejectRole)
        save = buttons.addButton("保存并刷新", QDialogButtonBox.AcceptRole)
        save.setObjectName("primaryButton")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._save)
        root.addWidget(buttons)

    def _choose_dbc(self) -> None:
        value, _ = QFileDialog.getOpenFileName(
            self, "选择 SpellIcon.dbc", "", "DBC 文件 (*.dbc);;所有文件 (*)"
        )
        if value:
            self.dbc_edit.setText(value)

    def _choose_root(self) -> None:
        value = QFileDialog.getExistingDirectory(self, "选择客户端解压根目录")
        if value:
            self.root_edit.setText(value)

    def _save(self) -> None:
        dbc = self.dbc_edit.text().strip()
        root = self.root_edit.text().strip()
        try:
            if bool(dbc) != bool(root):
                raise ValueError(
                    "SpellIcon.dbc 和客户端解压根目录需要同时填写，或同时清空。"
                )
            if dbc:
                dbc_path = Path(dbc).expanduser()
                root_path = Path(root).expanduser()
                if not dbc_path.is_file():
                    raise ValueError(f"SpellIcon.dbc 不存在：{dbc_path}")
                if not root_path.is_dir():
                    raise ValueError(f"客户端解压根目录不存在：{root_path}")
                if not spell_icon_resource_directories(root_path):
                    raise ValueError(
                        "客户端解压根目录下未找到 Interface/Icons、"
                        "Interface/Spellbook 或可直接使用的 BLP 目录"
                    )
                load_spell_icon_dbc(dbc_path)
            self.app.save_spell_icon_settings(dbc, root)
        except (OSError, ValueError, TypeError) as exc:
            _message_error(self, "图标资源配置无效", str(exc))
            return
        self.accept()


class CustomSkillEditorDialog(QDialog):
    def __init__(
        self,
        manager: "CustomSkillsDialog",
        original_group: str | None = None,
        original_skill: str | None = None,
    ):
        super().__init__(manager)
        self.manager = manager
        self.view = manager.view
        self.original_group = original_group
        self.original_skill = original_skill
        self.setWindowTitle("编辑自定义技能" if original_skill else "新增自定义技能")
        self.setMinimumSize(680, 680)
        _apply_saved_geometry(
            self,
            self.view.app.settings.dialog_geometries.get(
                CUSTOM_SKILL_EDITOR_GEOMETRY_KEY, ""
            ),
            "780x740",
        )
        self.setModal(True)

        current: dict = {}
        if original_group and original_skill:
            current = self.view.configuration[original_group][original_skill]
        initial_group = original_group or self.view.active_group.config_name

        self.group_box = QComboBox()
        for group in self.view.feature.config_groups:
            self.group_box.addItem(group.title, group.config_name)
        group_index = self.group_box.findData(initial_group)
        self.group_box.setCurrentIndex(max(group_index, 0))
        self.skill_edit = QLineEdit(original_skill or "")
        self.value_edit = QLineEdit(str(current.get("value", "")))
        self.enabled_check = QCheckBox("启用此技能修改")
        self.enabled_check.setChecked(bool(current.get("enabled", True)))
        self.template_box = QComboBox()
        for template in SKILL_CONDITION_TEMPLATES:
            self.template_box.addItem(template.title)
        self.template_help = QLabel()
        self.template_help.setWordWrap(True)
        self.condition_edit = QPlainTextEdit()
        if original_skill:
            self.condition_edit.setPlainText(
                self.view.custom_conditions.get(original_skill, "")
            )
        self.preview = QPlainTextEdit(
            "填写 WHERE 后的判断表达式，然后点击“测试查询”。"
        )
        self.preview.setReadOnly(True)
        self._build()
        self._template_selected()
        self.skill_edit.setFocus()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        title = QLabel("自定义职业技能")
        title.setObjectName("dialogTitle")
        subtitle = QLabel(
            "查询条件会同时用于读取当前值、技能描述、技能图标以及实际数据库修改。"
        )
        subtitle.setObjectName("muted")
        root.addWidget(title)
        root.addWidget(subtitle)

        form = QFormLayout()
        form.addRow("修改类型", self.group_box)
        form.addRow("技能定义名称", self.skill_edit)
        form.addRow("修改值", self.value_edit)
        form.addRow("", self.enabled_check)
        root.addLayout(form)

        template_row = QHBoxLayout()
        template_row.addWidget(QLabel("查询模板"))
        template_row.addWidget(self.template_box, 1)
        apply_template = QPushButton("套用模板")
        apply_template.clicked.connect(self._apply_condition_template)
        template_row.addWidget(apply_template)
        root.addLayout(template_row)
        self.template_help.setObjectName("muted")
        root.addWidget(self.template_help)
        root.addWidget(QLabel("查询条件（只填写 WHERE 后的表达式）"))
        root.addWidget(self.condition_edit, 3)
        root.addWidget(QLabel("查询预览"))
        root.addWidget(self.preview, 2)

        actions = QHBoxLayout()
        test_button = QPushButton("测试查询")
        cancel_button = QPushButton("取消")
        save_button = QPushButton("保存并查询")
        save_button.setObjectName("primaryButton")
        test_button.clicked.connect(self._test_query)
        cancel_button.clicked.connect(self.reject)
        save_button.clicked.connect(self._save)
        actions.addWidget(test_button)
        actions.addStretch(1)
        actions.addWidget(cancel_button)
        actions.addWidget(save_button)
        root.addLayout(actions)
        self.template_box.currentTextChanged.connect(self._template_selected)

    def _selected_condition_template(self):
        return SKILL_CONDITION_TEMPLATE_BY_TITLE.get(
            self.template_box.currentText(), SKILL_CONDITION_TEMPLATES[0]
        )

    def _template_selected(self) -> None:
        self.template_help.setText(self._selected_condition_template().description)

    def _apply_condition_template(self) -> None:
        template = self._selected_condition_template()
        self.template_help.setText(template.description)
        self.condition_edit.setPlainText(template.render(self.skill_edit.text()))
        self.condition_edit.setFocus()

    def _values(self) -> tuple[str, str, str, str, bool]:
        group_name = str(self.group_box.currentData() or "")
        skill = self.skill_edit.text().strip()
        value = self.value_edit.text().strip()
        condition = validate_skill_condition(self.condition_edit.toPlainText())
        if not skill:
            raise ValueError("技能定义名称不能为空。")
        if len(skill) > 80:
            raise ValueError("技能定义名称不能超过 80 个字符。")
        self.view.feature.validate_custom_skill_value(group_name, skill, value)
        return group_name, skill, value, condition, self.enabled_check.isChecked()

    def _test_query(self) -> None:
        try:
            condition = validate_skill_condition(self.condition_edit.toPlainText())
            QApplication.setOverrideCursor(Qt.WaitCursor)
            preview = preview_skill_condition(self.view.app.profile, condition)
        except Exception as exc:
            _message_error(self, "测试查询失败", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()
        lines = [f"匹配 {preview.count} 条 spell 记录（最多显示 20 条）："]
        if preview.rows:
            lines.extend(
                f"ID {row.get('spell_id')} · {row.get('spell_name') or '未命名'}"
                f" · {row.get('spell_rank') or '无等级'}"
                for row in preview.rows
            )
        else:
            lines.append("没有匹配结果，请检查条件或当前数据库版本。")
        self.preview.setPlainText("\n".join(lines))

    def _save(self) -> None:
        try:
            group_name, skill, value, condition, enabled = self._values()
            self.view.upsert_custom_skill(
                self.original_group,
                self.original_skill,
                group_name,
                skill,
                condition,
                value,
                enabled,
            )
        except ValueError as exc:
            _message_error(self, "自定义技能无效", str(exc))
            return
        self.manager.refresh_rows()
        self.accept()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.view.app.save_dialog_geometry(
            CUSTOM_SKILL_EDITOR_GEOMETRY_KEY, _geometry_string(self)
        )
        super().closeEvent(event)

    def accept(self) -> None:
        self.view.app.save_dialog_geometry(
            CUSTOM_SKILL_EDITOR_GEOMETRY_KEY, _geometry_string(self)
        )
        super().accept()

    def reject(self) -> None:
        self.view.app.save_dialog_geometry(
            CUSTOM_SKILL_EDITOR_GEOMETRY_KEY, _geometry_string(self)
        )
        super().reject()


class CustomSkillsDialog(QDialog):
    COLUMN_WIDTHS = (170, 54, 150, 64, 100, 360)

    def __init__(self, view: "SkillConfigView"):
        super().__init__(view)
        self.view = view
        self.setWindowTitle(f"{view.feature.title} · 管理自定义技能")
        self.setMinimumSize(760, 480)
        _apply_saved_geometry(
            self,
            self.view.app.settings.dialog_geometries.get(
                CUSTOM_SKILLS_DIALOG_GEOMETRY_KEY, ""
            ),
            "980x560",
        )
        self.setModal(True)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ("修改类型", "图标", "技能定义", "启用", "修改值", "查询条件")
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setWordWrap(True)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(lambda _index: self._edit())
        self.row_keys: dict[int, tuple[str, str]] = {}
        self._build()
        self.refresh_rows()
        self.view.add_icon_listener(self._icons_updated)

    def _build(self) -> None:
        root = QVBoxLayout(self)
        title = QLabel("管理自定义技能")
        title.setObjectName("dialogTitle")
        subtitle = QLabel(
            "这里新增的技能会参与图标、当前值、描述查询和实际应用；完成后请回到技能配置页点击“保存配置”。"
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("muted")
        root.addWidget(title)
        root.addWidget(subtitle)
        root.addWidget(self.table, 1)

        actions = QHBoxLayout()
        add_button = QPushButton("新增技能")
        add_button.setObjectName("primaryButton")
        edit_button = QPushButton("编辑")
        delete_button = QPushButton("删除")
        icon_button = QPushButton("图标资源")
        close_button = QPushButton("关闭")
        add_button.clicked.connect(self._add)
        edit_button.clicked.connect(self._edit)
        delete_button.clicked.connect(self._delete)
        icon_button.clicked.connect(self._configure_icons)
        close_button.clicked.connect(self.accept)
        actions.addWidget(add_button)
        actions.addWidget(edit_button)
        actions.addWidget(delete_button)
        actions.addWidget(icon_button)
        actions.addStretch(1)
        actions.addWidget(close_button)
        root.addLayout(actions)

    def refresh_rows(self) -> None:
        selected = self._selected()
        rows = self.view.custom_skill_rows()
        self.table.setRowCount(len(rows))
        self.row_keys.clear()
        for row_index, row_data in enumerate(rows):
            group_name, group_title, skill, enabled, value, condition = row_data
            self.row_keys[row_index] = (group_name, skill)
            values = (group_title, "", skill, "是" if enabled else "否", value, condition)
            for column, value_text in enumerate(values):
                item = QTableWidgetItem(str(value_text))
                if column in (1, 3):
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row_index, column, item)
            pixmap = self.view.skill_icon_pixmap(skill, 30)
            if pixmap is not None:
                self.table.item(row_index, 1).setIcon(QIcon(pixmap))
            self.table.setRowHeight(row_index, 44)
        for column, width in enumerate(self.COLUMN_WIDTHS):
            self.table.setColumnWidth(column, width)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        if selected is not None:
            for row, key in self.row_keys.items():
                if key == selected:
                    self.table.selectRow(row)
                    break

    def _selected(self) -> tuple[str, str] | None:
        row = self.table.currentRow()
        return self.row_keys.get(row)

    def _add(self) -> None:
        CustomSkillEditorDialog(self).exec_()

    def _edit(self, selected=None) -> None:
        key = selected if isinstance(selected, tuple) else self._selected()
        if key is None:
            _message_info(self, "请选择技能", "请先选择需要编辑的自定义技能。")
            return
        CustomSkillEditorDialog(self, *key).exec_()

    def _delete(self) -> None:
        selected = self._selected()
        if selected is None:
            _message_info(self, "请选择技能", "请先选择需要删除的自定义技能。")
            return
        group_name, skill = selected
        if not _confirm(
            self, "删除自定义技能", f"确定从此修改类型中删除“{skill}”吗？"
        ):
            return
        self.view.remove_custom_skill(group_name, skill)
        self.refresh_rows()

    def _configure_icons(self) -> None:
        IconResourcesDialog(self.view.app, self).exec_()

    def _icons_updated(self, _changed=None) -> None:
        self.refresh_rows()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.view.remove_icon_listener(self._icons_updated)
        self.view.app.save_dialog_geometry(
            CUSTOM_SKILLS_DIALOG_GEOMETRY_KEY, _geometry_string(self)
        )
        super().closeEvent(event)

    def accept(self) -> None:
        self.view.remove_icon_listener(self._icons_updated)
        self.view.app.save_dialog_geometry(
            CUSTOM_SKILLS_DIALOG_GEOMETRY_KEY, _geometry_string(self)
        )
        super().accept()

    def reject(self) -> None:
        self.view.remove_icon_listener(self._icons_updated)
        self.view.app.save_dialog_geometry(
            CUSTOM_SKILLS_DIALOG_GEOMETRY_KEY, _geometry_string(self)
        )
        super().reject()


class SkillConfigView(QWidget):
    HEADERS = ("启用", "图标", "技能", "修改值", "当前值", "技能描述")

    def __init__(
        self,
        app: "DbToolApp",
        feature: Feature,
        navigation_state: dict | None = None,
    ):
        super().__init__()
        self.app = app
        self.feature = feature
        navigation_state = navigation_state or {}
        saved = navigation_state.get(
            "configuration", app.settings.feature_configs.get(feature.id, {})
        )
        normalized = feature.normalize_configuration(saved)
        self.custom_conditions = dict(normalized.pop(CUSTOM_SKILL_CONDITIONS_KEY, {}))
        self.configuration = normalized
        self.group_scroll_positions = dict(
            navigation_state.get("group_scroll_positions", {})
        )
        self.preserve_navigation_state = True
        active_group_name = navigation_state.get("active_group")
        self.active_group = next(
            (
                group
                for group in feature.config_groups
                if group.config_name == active_group_name
            ),
            feature.config_groups[0],
        )
        self.icon_paths: dict[str, Path] = {}
        self.icon_listeners: list[Callable] = []
        self.tables: dict[str, QTableWidget] = {}
        self.group_indexes: dict[str, int] = {}
        self.enabled_widgets: dict[tuple[str, str], QCheckBox] = {}
        self.value_widgets: dict[tuple[str, str], QLineEdit] = {}
        self.current_items: dict[tuple[str, str], QTableWidgetItem] = {}
        self.description_items: dict[str, list[QTableWidgetItem]] = {}
        self.detail_request_id = 0
        cached_loader = getattr(self.app, "cached_skill_icons", None)
        if cached_loader:
            self.icon_paths = cached_loader(self.feature, self._configuration_snapshot())
        self._build()
        self._rebuild_groups(sync=False)
        self._activate_group(self.active_group.config_name)
        self._update_summary()
        self._request_details()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 22)
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        self.title_label = QLabel(self.feature.title)
        self.title_label.setObjectName("pageTitle")
        self.summary_label = QLabel()
        self.summary_label.setObjectName("muted")
        title_box.addWidget(self.title_label)
        title_box.addWidget(self.summary_label)
        header.addLayout(title_box, 1)

        icon_button = QPushButton("图标资源")
        custom_button = QPushButton("管理自定义技能")
        reset_button = QPushButton("恢复代码默认值")
        save_button = QPushButton("保存配置")
        back_button = QPushButton("← 返回职业技能")
        save_button.setObjectName("primaryButton")
        icon_button.clicked.connect(self._configure_icon_resources)
        custom_button.clicked.connect(self._manage_custom_skills)
        reset_button.clicked.connect(self._reset_defaults)
        save_button.clicked.connect(self._save)
        back_button.clicked.connect(self._back)
        for button in (icon_button, custom_button, reset_button, save_button, back_button):
            header.addWidget(button)
        root.addLayout(header)

        self.description_status = QLabel("正在从当前数据库读取技能当前值与描述")
        self.description_status.setObjectName("muted")
        self.icon_status = QLabel(
            f"图标：已加载缓存 {len(self.icon_paths)} 项，正在同步数据库"
            if self.icon_paths
            else "图标：正在同步数据库与本地缓存"
        )
        self.icon_status.setObjectName("muted")
        status_row = QHBoxLayout()
        status_row.addWidget(self.description_status)
        status_row.addStretch(1)
        status_row.addWidget(self.icon_status)
        root.addLayout(status_row)

        splitter = QSplitter(Qt.Horizontal)
        self.group_list = QListWidget()
        self.group_list.setMinimumWidth(190)
        self.group_list.setMaximumWidth(280)
        self.group_list.currentRowChanged.connect(self._group_changed)
        self.group_stack = QStackedWidget()
        splitter.addWidget(self.group_list)
        splitter.addWidget(self.group_stack)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([220, 900])
        root.addWidget(splitter, 1)

    def _configuration_snapshot(self) -> dict:
        result = copy.deepcopy(self.configuration)
        for key, checkbox in self.enabled_widgets.items():
            group_name, skill = key
            if skill in result.get(group_name, {}):
                result[group_name][skill]["enabled"] = checkbox.isChecked()
        for key, edit in self.value_widgets.items():
            group_name, skill = key
            if skill in result.get(group_name, {}):
                result[group_name][skill]["value"] = edit.text()
        result[CUSTOM_SKILL_CONDITIONS_KEY] = dict(self.custom_conditions)
        return result

    def _sync_widgets_to_configuration(self) -> None:
        snapshot = self._configuration_snapshot()
        self.custom_conditions = dict(snapshot.pop(CUSTOM_SKILL_CONDITIONS_KEY, {}))
        self.configuration = snapshot

    def _new_table(self, group_name: str) -> QTableWidget:
        table = QTableWidget(0, len(self.HEADERS))
        table.setHorizontalHeaderLabels(self.HEADERS)
        table.verticalHeader().setVisible(False)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setWordWrap(True)
        table.setIconSize(QSize(38, 38))
        header = table.horizontalHeader()
        widths = (58, 58, 150, 170, 145)
        for column, width in enumerate(widths):
            header.setSectionResizeMode(column, QHeaderView.Fixed)
            table.setColumnWidth(column, width)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        table.setProperty("group_name", group_name)
        return table

    def _rebuild_groups(self, *, sync: bool = True) -> None:
        if sync:
            self._sync_widgets_to_configuration()
        current_group = self.active_group.config_name
        scrolls = dict(self.group_scroll_positions)
        scrolls.update(
            {
                name: table.verticalScrollBar().value()
                for name, table in self.tables.items()
            }
        )
        self.group_list.blockSignals(True)
        self.group_list.clear()
        while self.group_stack.count():
            widget = self.group_stack.widget(0)
            self.group_stack.removeWidget(widget)
            widget.deleteLater()
        self.tables.clear()
        self.group_indexes.clear()
        self.enabled_widgets.clear()
        self.value_widgets.clear()
        self.current_items.clear()
        self.description_items.clear()

        for index, group in enumerate(self.feature.config_groups):
            count = len(self.configuration[group.config_name])
            self.group_list.addItem(f"{group.title}  ({count})")
            table = self._new_table(group.config_name)
            self.tables[group.config_name] = table
            self.group_indexes[group.config_name] = index
            self.group_stack.addWidget(table)
            skills = self.configuration[group.config_name]
            table.setRowCount(len(skills))
            for row, (skill, item) in enumerate(skills.items()):
                key = (group.config_name, skill)
                enabled = QCheckBox()
                enabled.setChecked(bool(item["enabled"]))
                enabled.setStyleSheet("margin-left: 16px;")
                value_edit = QLineEdit(str(item["value"]))
                value_edit.setMinimumWidth(120)
                table.setCellWidget(row, 0, enabled)
                icon_item = QTableWidgetItem()
                icon_item.setTextAlignment(Qt.AlignCenter)
                pixmap = self.skill_icon_pixmap(skill, 38)
                if pixmap is not None:
                    icon_item.setIcon(QIcon(pixmap))
                else:
                    icon_item.setText("—")
                table.setItem(row, 1, icon_item)
                skill_item = QTableWidgetItem(skill)
                table.setItem(row, 2, skill_item)
                value_holder = QWidget()
                value_layout = QHBoxLayout(value_holder)
                value_layout.setContentsMargins(6, 4, 6, 4)
                value_layout.addWidget(value_edit)
                table.setCellWidget(row, 3, value_holder)
                current_item = QTableWidgetItem("正在读取…")
                description_item = QTableWidgetItem("正在从当前数据库读取…")
                table.setItem(row, 4, current_item)
                table.setItem(row, 5, description_item)
                table.setRowHeight(row, 54)
                self.enabled_widgets[key] = enabled
                self.value_widgets[key] = value_edit
                self.current_items[key] = current_item
                self.description_items.setdefault(skill, []).append(description_item)
                enabled.toggled.connect(self._update_summary)
            scroll_value = int(scrolls.get(group.config_name, 0))
            QTimer.singleShot(
                0, lambda target=table, value=scroll_value: _restore_scroll_value(target, value)
            )
        self.group_list.blockSignals(False)
        self._activate_group(current_group)

    def _group_changed(self, row: int) -> None:
        if row < 0 or row >= len(self.feature.config_groups):
            return
        previous = self.active_group.config_name
        if previous in self.tables:
            self.group_scroll_positions[previous] = self.tables[
                previous
            ].verticalScrollBar().value()
        self.active_group = self.feature.config_groups[row]
        self.group_stack.setCurrentIndex(row)
        table = self.tables[self.active_group.config_name]
        table.verticalScrollBar().setValue(
            int(self.group_scroll_positions.get(self.active_group.config_name, 0))
        )

    def _activate_group(self, group_name: str) -> None:
        index = self.group_indexes.get(group_name, 0)
        self.active_group = self.feature.config_groups[index]
        self.group_list.setCurrentRow(index)
        self.group_stack.setCurrentIndex(index)

    def _update_summary(self) -> None:
        enabled = sum(checkbox.isChecked() for checkbox in self.enabled_widgets.values())
        total = len(self.enabled_widgets)
        custom = len(self.custom_conditions)
        text = f"已启用 {enabled} / {total} 项技能"
        if custom:
            text += f" · GUI 自定义技能 {custom} 项"
        self.summary_label.setText(text)

    def _collect(self) -> dict:
        return self._configuration_snapshot()

    def navigation_state(self) -> dict:
        for name, table in self.tables.items():
            self.group_scroll_positions[name] = table.verticalScrollBar().value()
        return {
            "configuration": self._collect(),
            "active_group": self.active_group.config_name,
            "group_scroll_positions": dict(self.group_scroll_positions),
        }

    def skill_icon_pixmap(self, skill: str, size: int = 34) -> QPixmap | None:
        path = self.icon_paths.get(skill)
        return _load_qpixmap(path, size) if path else None

    def add_icon_listener(self, callback: Callable) -> None:
        if callback not in self.icon_listeners:
            self.icon_listeners.append(callback)

    def remove_icon_listener(self, callback: Callable) -> None:
        try:
            self.icon_listeners.remove(callback)
        except ValueError:
            pass

    def _notify_icon_listeners(self, changed) -> None:
        for callback in list(self.icon_listeners):
            try:
                callback(changed)
            except RuntimeError:
                self.remove_icon_listener(callback)

    def _request_details(self) -> None:
        self.detail_request_id += 1
        request_id = self.detail_request_id
        self.description_status.setText("正在从当前数据库读取技能当前值与描述")
        configuration = self._collect()

        def callback(descriptions, current_values, error, icon_result=None):
            if request_id != self.detail_request_id:
                return
            self._details_loaded(
                descriptions,
                current_values,
                error,
                icon_result or SpellIconSyncResult({}),
            )

        self.app.request_skill_details(self.feature, callback, configuration)

    def _details_loaded(
        self,
        descriptions: dict[str, str],
        current_values: dict[tuple[str, str], str],
        error: str,
        icon_result: SpellIconSyncResult,
    ) -> None:
        if error:
            self.description_status.setText(f"读取失败：{error}")
        else:
            self.description_status.setText("当前值与技能描述已从数据库更新")
        for key, item in self.current_items.items():
            item.setText(current_values.get(key) or ("读取失败" if error else "无匹配值"))
        for skill, items in self.description_items.items():
            value = descriptions.get(skill) or ("读取失败" if error else "数据库中没有描述")
            for item in items:
                item.setText(value)
        self.icon_paths = dict(icon_result.paths)
        if icon_result.changed_skills:
            self._refresh_table_icons(icon_result.changed_skills)
        if icon_result.error:
            self.icon_status.setText(f"图标：{icon_result.error}")
        else:
            self.icon_status.setText(f"图标：缓存已同步，共 {len(self.icon_paths)} 项")
        if icon_result.changed_skills:
            self._notify_icon_listeners(icon_result.changed_skills)

    def _refresh_table_icons(self, changed=None) -> None:
        changed_set = set(changed or self.icon_paths)
        for group_name, table in self.tables.items():
            for row, skill in enumerate(self.configuration[group_name]):
                if skill not in changed_set:
                    continue
                item = table.item(row, 1)
                pixmap = self.skill_icon_pixmap(skill, 38)
                item.setIcon(QIcon(pixmap) if pixmap is not None else QIcon())
                item.setText("" if pixmap is not None else "—")

    def refresh_icon_resources(self) -> None:
        try:
            self.icon_paths = self.app.cached_skill_icons(self.feature, self._collect())
        except Exception:
            self.icon_paths = {}
        self._refresh_table_icons()
        self.icon_status.setText(
            f"图标：已加载缓存 {len(self.icon_paths)} 项，正在同步数据库"
        )
        self._request_details()

    def _configure_icon_resources(self) -> None:
        IconResourcesDialog(self.app, self).exec_()

    def _manage_custom_skills(self) -> None:
        CustomSkillsDialog(self).exec_()

    def custom_skill_rows(self):
        self._sync_widgets_to_configuration()
        rows = []
        for group in self.feature.config_groups:
            for skill, item in self.configuration[group.config_name].items():
                if skill not in self.custom_conditions:
                    continue
                rows.append(
                    (
                        group.config_name,
                        group.title,
                        skill,
                        bool(item["enabled"]),
                        str(item["value"]),
                        self.custom_conditions[skill],
                    )
                )
        return rows

    def upsert_custom_skill(
        self,
        original_group: str | None,
        original_skill: str | None,
        group_name: str,
        skill: str,
        condition: str,
        value: str,
        enabled: bool,
    ) -> None:
        self._sync_widgets_to_configuration()
        skill = str(skill or "").strip()
        condition = validate_skill_condition(condition)
        self.feature.validate_custom_skill_value(group_name, skill, value)
        module = importlib.import_module(self.feature.module)
        if skill in module.cond:
            raise ValueError(
                f"“{skill}”已经由职业代码中的 cond 定义，请直接配置现有技能或使用不同的自定义名称。"
            )
        if group_name not in self.configuration:
            raise ValueError("请选择有效的技能修改类型。")
        existing = skill in self.configuration[group_name]
        same_row = original_group == group_name and original_skill == skill
        if existing and not same_row:
            raise ValueError(f"当前修改类型中已经存在“{skill}”。")
        if original_group and original_skill:
            if original_skill not in self.custom_conditions:
                raise ValueError("只能通过此窗口编辑 GUI 中新增的技能。")
            self.configuration[original_group].pop(original_skill, None)
        self.configuration[group_name][skill] = {
            "enabled": bool(enabled),
            "value": str(value).strip(),
        }
        self.custom_conditions[skill] = condition
        if original_skill and original_skill != skill:
            still_used = any(
                original_skill in self.configuration[group.config_name]
                for group in self.feature.config_groups
            )
            if not still_used:
                self.custom_conditions.pop(original_skill, None)
        self.active_group = next(
            group for group in self.feature.config_groups if group.config_name == group_name
        )
        self._rebuild_groups()
        self._update_summary()
        self._request_details()

    def remove_custom_skill(self, group_name: str, skill: str) -> None:
        self._sync_widgets_to_configuration()
        if skill not in self.custom_conditions:
            raise ValueError("只能删除 GUI 中新增的技能。")
        self.configuration[group_name].pop(skill, None)
        still_used = any(
            skill in self.configuration[group.config_name]
            for group in self.feature.config_groups
        )
        if not still_used:
            self.custom_conditions.pop(skill, None)
        self._rebuild_groups()
        self._update_summary()
        self._request_details()

    def _reset_defaults(self) -> None:
        if not _confirm(
            self,
            "恢复默认配置",
            "将所有技能恢复为当前代码中的默认启用状态和数值，并删除 GUI 中新增的自定义技能？",
        ):
            return
        self.configuration = self.feature.default_configuration()
        self.custom_conditions = {}
        self._rebuild_groups(sync=False)
        self._update_summary()
        self._request_details()

    def _save(self) -> None:
        configuration = self._collect()
        try:
            self.feature.configured_values(configuration)
            self.app.save_feature_configuration(self.feature, configuration)
        except (OSError, TypeError, ValueError) as exc:
            _message_error(self, "保存配置失败", str(exc))
            return
        self._back()

    def _back(self) -> None:
        self.preserve_navigation_state = False
        self.app.show_skill_category_home(self.feature)


class DbToolApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings: AppSettings = load_settings()
        self.spell_icon_cache = self._create_spell_icon_cache()
        self.setWindowTitle("Azeroth DB Forge")
        self.setMinimumSize(1040, 680)
        _apply_saved_geometry(self, self.settings.window_geometry, "1280x800")
        self.latest: dict[str, FeatureRun] = {}
        self.category = "全部功能"
        self.selected: dict[str, bool] = {feature.id: False for feature in FEATURES}
        self.skill_detail_callbacks: dict[tuple[object, ...], list[Callable]] = {}
        self.skill_navigation_states: dict[str, dict] = {}
        self.active_skill_feature_id: str | None = None
        self.current_skill_view: SkillConfigView | None = None
        self.running = False
        self.cards_frame: ScrollFrame | None = None
        self._signals = _WorkerSignals(self)
        self._signals.state_ready.connect(self._state_ready)
        self._signals.run_progress.connect(self._run_progress)
        self._signals.run_finished.connect(self._runs_finished)
        self._signals.skill_details_ready.connect(self._handle_skill_details)
        self._configure_styles()
        self._build_shell()
        self._reload_profile_widgets(refresh=False)
        self.show_features()
        threading.Thread(
            target=self._refresh_worker,
            args=(replace(self.profile),),
            daemon=True,
        ).start()

    @property
    def profile(self) -> DatabaseProfile:
        return self.settings.profiles[self.settings.selected_profile]

    def _create_spell_icon_cache(self) -> SpellIconCache:
        suggested_dbc, suggested_root = suggested_spell_icon_paths()
        return SpellIconCache(
            self.settings.spell_icon_dbc_path or suggested_dbc,
            self.settings.spell_icon_client_root or suggested_root,
        )

    def cached_skill_icons(self, feature: Feature, configuration) -> dict[str, Path]:
        return self.spell_icon_cache.cached_paths(self.profile, feature, configuration)

    def save_spell_icon_settings(self, dbc_file: str, client_root: str) -> None:
        updated = replace(
            self.settings,
            spell_icon_dbc_path=str(dbc_file or "").strip(),
            spell_icon_client_root=str(client_root or "").strip(),
        )
        save_settings(updated)
        self.settings = updated
        self.spell_icon_cache = self._create_spell_icon_cache()
        if self.current_skill_view is not None:
            self.current_skill_view.refresh_icon_resources()

    def feature_configuration(self, feature: Feature):
        if not feature.configurable:
            return None
        return feature.normalize_configuration(
            self.settings.feature_configs.get(feature.id, {})
        )

    def feature_version(self, feature: Feature) -> str:
        return feature.effective_version(self.feature_configuration(feature))

    def save_feature_configuration(self, feature: Feature, configuration) -> None:
        normalized = feature.normalize_configuration(configuration)
        feature.configured_values(normalized)
        feature_configs = copy.deepcopy(self.settings.feature_configs)
        feature_configs[feature.id] = normalized
        updated = replace(self.settings, feature_configs=feature_configs)
        save_settings(updated)
        self.settings = updated

    def _configure_styles(self) -> None:
        application = QApplication.instance()
        if application is not None:
            application.setFont(QFont("Noto Sans CJK SC", 9))
        self.setStyleSheet(
            f"""
            QMainWindow, QDialog, QWidget#pageRoot {{ background: {COLORS['paper']}; }}
            QWidget {{ color: {COLORS['ink']}; }}
            QLabel#pageTitle {{ font-size: 22px; font-weight: 700; }}
            QLabel#dialogTitle {{ font-size: 19px; font-weight: 700; }}
            QLabel#muted {{ color: {COLORS['muted']}; }}
            QLineEdit, QComboBox, QListWidget, QTableWidget, QPlainTextEdit {{
                background: white; border: 1px solid {COLORS['line']};
                border-radius: 5px; padding: 5px;
            }}
            QPushButton {{
                background: white; border: 1px solid {COLORS['line']};
                border-radius: 5px; padding: 7px 12px;
            }}
            QPushButton:hover {{ background: {COLORS['blue_soft']}; }}
            QPushButton#primaryButton {{
                color: white; background: {COLORS['gold']}; border-color: {COLORS['gold']};
                font-weight: 700;
            }}
            QPushButton#primaryButton:hover {{ background: #AE7624; }}
            QHeaderView::section {{
                background: {COLORS['slate_soft']}; color: {COLORS['muted']};
                border: 0; border-bottom: 1px solid {COLORS['line']};
                padding: 7px; font-weight: 700;
            }}
            QTableWidget {{ gridline-color: {COLORS['line']}; }}
            QFrame#featureCard {{
                background: white; border: 1px solid {COLORS['line']}; border-radius: 7px;
            }}
            QFrame#topBar {{ background: {COLORS['navy']}; }}
            QFrame#sideBar {{ background: #1D3651; }}
            QPushButton#navButton {{
                text-align: left; color: #DCE7F0; background: transparent;
                border: 0; padding: 10px 14px;
            }}
            QPushButton#navButton:hover {{ background: {COLORS['navy_2']}; }}
            """
        )

    def _build_shell(self) -> None:
        central = QWidget()
        central.setObjectName("pageRoot")
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        top = QFrame()
        top.setObjectName("topBar")
        top.setFixedHeight(76)
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(24, 8, 22, 8)
        brand = QLabel("<span style='color:#9CC4D2;font-size:10px'>AZEROTH</span><br>"
                       "<span style='color:white;font-size:22px;font-weight:700'>DB FORGE</span>")
        top_layout.addWidget(brand)
        top_layout.addStretch(1)
        target_box = QVBoxLayout()
        self.connection_label = QLabel("尚未连接")
        self.connection_label.setStyleSheet("color:#C7D3E0")
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(240)
        self.profile_combo.currentIndexChanged.connect(self._profile_changed)
        target_box.addWidget(self.connection_label)
        target_box.addWidget(self.profile_combo)
        top_layout.addLayout(target_box)
        profile_button = QPushButton("连接配置")
        profile_button.clicked.connect(lambda: ProfilesDialog(self).exec_())
        top_layout.addWidget(profile_button)
        root.addWidget(top)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sideBar")
        sidebar.setFixedWidth(205)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(16, 20, 16, 18)
        all_button = self._nav_button("全部功能", lambda: self._set_category("全部功能"))
        side_layout.addWidget(all_button)
        for category in CATEGORIES:
            side_layout.addWidget(
                self._nav_button(category, lambda checked=False, name=category: self._set_category(name))
            )
        side_layout.addSpacing(12)
        side_layout.addWidget(self._nav_button("执行历史", self.show_history))
        side_layout.addStretch(1)
        selected_button = QPushButton("应用已勾选功能")
        selected_button.setObjectName("primaryButton")
        selected_button.clicked.connect(self.apply_selected)
        side_layout.addWidget(selected_button)
        body_layout.addWidget(sidebar)

        self.main_host = QWidget()
        self.main_layout = QVBoxLayout(self.main_host)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.addWidget(self.main_host, 1)
        root.addWidget(body, 1)
        self.setCentralWidget(central)

    def _nav_button(self, text: str, command: Callable) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("navButton")
        button.clicked.connect(command)
        return button

    def _clear_main(self) -> None:
        if self.current_skill_view is not None:
            if self.current_skill_view.preserve_navigation_state:
                self.skill_navigation_states[
                    self.current_skill_view.feature.id
                ] = self.current_skill_view.navigation_state()
            self.current_skill_view = None
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _set_category(self, category: str) -> None:
        if category == "职业技能" and self.active_skill_feature_id:
            feature = next(
                (item for item in FEATURES if item.id == self.active_skill_feature_id),
                None,
            )
            if feature is not None:
                self.show_skill_configuration(feature)
                return
        self.category = category
        self.show_features()

    def show_features(self) -> None:
        self._clear_main()
        page = QWidget()
        page.setObjectName("pageRoot")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        header = QHBoxLayout()
        title = QLabel(self.category)
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch(1)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索功能…")
        self.search_edit.setMaximumWidth(300)
        self.search_edit.textChanged.connect(self._render_cards)
        self.status_combo = QComboBox()
        self.status_combo.addItems(("全部状态", "未应用", "已应用", "有更新", "失败"))
        self.status_combo.currentTextChanged.connect(self._render_cards)
        refresh_button = QPushButton("刷新状态")
        refresh_button.clicked.connect(self.refresh_state)
        header.addWidget(self.search_edit)
        header.addWidget(self.status_combo)
        header.addWidget(refresh_button)
        layout.addLayout(header)

        self.summary_label = QLabel()
        self.summary_label.setObjectName("muted")
        layout.addWidget(self.summary_label)
        self.cards_frame = ScrollFrame()
        layout.addWidget(self.cards_frame, 1)
        self.main_layout.addWidget(page)
        self._render_cards()

    def _run_status(self, feature: Feature) -> str:
        run = self.latest.get(feature.id)
        if run is None:
            return "none"
        if run.status in ("applied", "marked") and run.feature_version != self.feature_version(feature):
            return "updated"
        return run.status if run.status in STATUS_STYLE else "none"

    def _filtered_features(self):
        query = self.search_edit.text().strip().lower() if hasattr(self, "search_edit") else ""
        status_filter = self.status_combo.currentText() if hasattr(self, "status_combo") else "全部状态"
        for feature in FEATURES:
            if self.category != "全部功能" and feature.category != self.category:
                continue
            if query and query not in (feature.title + feature.description + feature.id).lower():
                continue
            status = self._run_status(feature)
            if status_filter == "未应用" and status != "none":
                continue
            if status_filter == "已应用" and status not in ("applied", "marked"):
                continue
            if status_filter == "有更新" and status != "updated":
                continue
            if status_filter == "失败" and status != "failed":
                continue
            yield feature

    def _render_cards(self) -> None:
        if self.cards_frame is None:
            return
        self.cards_frame.clear()
        features = list(self._filtered_features())
        statuses = [self._run_status(feature) for feature in FEATURES]
        self.summary_label.setText(
            f"共 {len(FEATURES)} 项 · 已应用 {sum(s in ('applied', 'marked') for s in statuses)} "
            f"· 有更新 {statuses.count('updated')} · 失败 {statuses.count('failed')}"
        )
        if not features:
            empty = QLabel("没有匹配的功能")
            empty.setAlignment(Qt.AlignCenter)
            empty.setMinimumHeight(180)
            self.cards_frame.add_widget(empty)
            return
        for feature in features:
            self.cards_frame.add_widget(self._create_feature_card(feature))

    def _create_feature_card(self, feature: Feature) -> QFrame:
        status_key = self._run_status(feature)
        status_text, status_fg, status_bg = STATUS_STYLE[status_key]
        card = QFrame()
        card.setObjectName("featureCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        check = QCheckBox()
        check.setChecked(self.selected[feature.id])
        check.toggled.connect(lambda value, feature_id=feature.id: self.selected.__setitem__(feature_id, value))
        layout.addWidget(check)
        text_box = QVBoxLayout()
        title_row = QHBoxLayout()
        title = QLabel(feature.title)
        title.setStyleSheet("font-size:15px;font-weight:700")
        badge = QLabel(status_text)
        badge.setStyleSheet(
            f"color:{status_fg};background:{status_bg};padding:3px 8px;border-radius:4px;font-weight:700"
        )
        title_row.addWidget(title)
        title_row.addWidget(badge)
        if feature.risk == "high":
            risk = QLabel("高影响")
            risk.setStyleSheet(
                f"color:{COLORS['red']};background:{COLORS['red_soft']};padding:3px 7px;border-radius:4px"
            )
            title_row.addWidget(risk)
        title_row.addStretch(1)
        text_box.addLayout(title_row)
        description = QLabel(feature.description)
        description.setWordWrap(True)
        description.setObjectName("muted")
        text_box.addWidget(description)
        if feature.configurable:
            enabled, total = feature.configuration_summary(self.feature_configuration(feature))
            configured = QLabel(f"技能配置：已启用 {enabled} / {total} 项")
            configured.setStyleSheet(f"color:{COLORS['teal']};font-weight:700")
            text_box.addWidget(configured)
        run = self.latest.get(feature.id)
        meta = f"{feature.id} · 版本 {self.feature_version(feature)}"
        if run and run.finished_at:
            meta += f" · 最近 {run.finished_at}"
        meta_label = QLabel(meta)
        meta_label.setObjectName("muted")
        text_box.addWidget(meta_label)
        layout.addLayout(text_box, 1)

        actions = QVBoxLayout()
        if feature.configurable:
            config_button = QPushButton("配置技能")
            config_button.clicked.connect(lambda _checked=False, value=feature: self.show_skill_configuration(value))
            actions.addWidget(config_button)
        details_button = QPushButton("记录详情")
        apply_button = QPushButton("应用功能")
        mark_button = QPushButton("仅标记已应用")
        apply_button.setObjectName("primaryButton")
        details_button.clicked.connect(lambda _checked=False, value=feature: self.show_feature_details(value))
        apply_button.clicked.connect(lambda _checked=False, value=feature: self.apply_features([value]))
        mark_button.clicked.connect(lambda _checked=False, value=feature: self.mark_feature(value))
        actions.addWidget(details_button)
        actions.addWidget(apply_button)
        actions.addWidget(mark_button)
        layout.addLayout(actions)
        return card

    def show_skill_configuration(self, feature: Feature) -> None:
        if not feature.configurable:
            return
        self.category = feature.category
        self.active_skill_feature_id = feature.id
        self._clear_main()
        self.current_skill_view = SkillConfigView(
            self, feature, self.skill_navigation_states.get(feature.id)
        )
        self.main_layout.addWidget(self.current_skill_view)

    def show_skill_category_home(self, feature: Feature | None = None) -> None:
        feature_id = feature.id if feature is not None else self.active_skill_feature_id
        if feature_id:
            self.skill_navigation_states.pop(feature_id, None)
        self.active_skill_feature_id = None
        self.category = "职业技能"
        self.show_features()

    def apply_selected(self) -> None:
        features = [feature for feature in FEATURES if self.selected[feature.id]]
        if not features:
            _message_info(self, "未选择功能", "请先勾选至少一个功能。")
            return
        self.apply_features(features)

    def apply_features(self, features: list[Feature]) -> None:
        if self.running:
            _message_info(self, "正在执行", "请等待当前功能执行完成。")
            return
        configurations = {
            feature.id: self.feature_configuration(feature) for feature in features
        }
        try:
            for feature in features:
                if not feature.configurable:
                    continue
                enabled, _total = feature.configuration_summary(configurations[feature.id])
                if enabled == 0:
                    raise ValueError(f"{feature.title}：没有勾选任何技能，请先打开“配置技能”。")
                feature.configured_values(configurations[feature.id])
        except ValueError as exc:
            _message_error(self, "技能配置无效", str(exc))
            return

        repeated = [feature.title for feature in features if self._run_status(feature) in ("applied", "marked")]
        high = [feature.title for feature in features if feature.risk == "high"]
        lines = []
        for feature in features:
            line = f"• {feature.title}"
            if feature.configurable:
                enabled, total = feature.configuration_summary(configurations[feature.id])
                line += f"（{enabled}/{total} 个技能）"
            lines.append(line)
        detail = f"目标：{self.profile.target_label}\n\n将执行：\n" + "\n".join(lines)
        if repeated:
            detail += "\n\n以下功能已经应用过，重复执行可能继续叠加数值：\n" + "\n".join(f"• {name}" for name in repeated)
        if high:
            detail += "\n\n高影响功能：\n" + "\n".join(f"• {name}" for name in high) + "\n建议先备份数据库。"
        if not _confirm(self, "确认应用功能", detail, bool(high or repeated)):
            return
        self.running = True
        self.connection_label.setText(f"执行中 · {self.profile.name}")
        threading.Thread(
            target=self._run_many_worker,
            args=(replace(self.profile), features, configurations),
            daemon=True,
        ).start()

    def _run_many_worker(self, profile, features, configurations) -> None:
        results = []
        for feature in features:
            try:
                result = run_feature(profile, feature, configurations.get(feature.id))
            except Exception:
                error = traceback.format_exc()
                result = RunResult(False, feature, 0, error, error)
            results.append(result)
            self._signals.run_progress.emit(result)
            if not result.ok:
                break
        self._signals.run_finished.emit(results)

    def _run_progress(self, result: RunResult) -> None:
        self.connection_label.setText(
            f"{'完成' if result.ok else '失败'} · {result.feature.title}"
        )
        self.refresh_state()

    def _runs_finished(self, results: list[RunResult]) -> None:
        self.running = False
        self.connection_label.setText(f"已连接 · {self.profile.name}")
        self._render_cards()
        failures = [result for result in results if not result.ok]
        if failures:
            result = failures[0]
            _message_error(self, "执行失败", result.error or result.output)
            self.show_result_log(result)
        elif results:
            _message_info(self, "执行完成", f"已完成 {len(results)} 项功能。")

    def mark_feature(self, feature: Feature) -> None:
        if self.running:
            return
        configuration = self.feature_configuration(feature)
        note = "由用户手动标记为已应用"
        try:
            if feature.configurable:
                enabled, total = feature.configuration_summary(configuration)
                if enabled == 0:
                    raise ValueError(f"{feature.title}：没有勾选任何技能，请先打开“配置技能”。")
                configured = feature.configured_values(configuration)
                note += f"\n当前技能配置：{enabled}/{total} 项"
                for group in feature.config_groups:
                    values = configured[group.config_name]
                    if values:
                        note += f"\n[{group.title}] {len(values)} 项"
                        note += "".join(f"\n  - {skill}: {value}" for skill, value in values.items())
        except ValueError as exc:
            _message_error(self, "技能配置无效", str(exc))
            return
        if not _confirm(self, "仅标记已应用", f"不会执行数据库修改，只记录：\n\n{feature.title}\n{self.profile.target_label}"):
            return
        try:
            FeatureStateStore(self.profile).mark_applied(
                feature.id, feature.title, self.feature_version(feature), note
            )
            self.refresh_state()
        except Exception as exc:
            _message_error(self, "标记失败", str(exc))

    def request_skill_details(self, feature: Feature, callback: Callable, configuration=None) -> None:
        normalized = feature.normalize_configuration(configuration)
        icon_cache = self.spell_icon_cache
        key = (
            self.profile.target_label,
            id(icon_cache),
            feature.id,
            feature.effective_version(normalized),
        )
        callbacks = self.skill_detail_callbacks.setdefault(key, [])
        callbacks.append(callback)
        if len(callbacks) > 1:
            return
        threading.Thread(
            target=self._skill_detail_worker,
            args=(replace(self.profile), feature, copy.deepcopy(normalized), key, icon_cache),
            daemon=True,
        ).start()

    def _skill_detail_worker(self, profile, feature, configuration, key, icon_cache) -> None:
        try:
            details = load_skill_details(profile, feature, configuration)
            icon_result = icon_cache.sync(profile, feature, configuration, details.icons)
            self._signals.skill_details_ready.emit(
                key, details.descriptions, details.current_values, "", icon_result
            )
        except Exception as exc:
            try:
                cached = icon_cache.cached_paths(profile, feature, configuration)
            except Exception:
                cached = {}
            error = str(exc)
            self._signals.skill_details_ready.emit(
                key, {}, {}, error, SpellIconSyncResult(cached, error=error)
            )

    def _handle_skill_details(self, key, descriptions, current_values, error, icon_result) -> None:
        callbacks = self.skill_detail_callbacks.pop(tuple(key), [])
        for callback in callbacks:
            self._deliver_skill_details(callback, descriptions, current_values, error, icon_result)

    @staticmethod
    def _deliver_skill_details(callback, descriptions, current_values, error, icon_result) -> None:
        try:
            parameters = tuple(inspect.signature(callback).parameters.values())
            accepts_icons = any(parameter.kind == inspect.Parameter.VAR_POSITIONAL for parameter in parameters) or sum(
                parameter.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
                for parameter in parameters
            ) >= 4
        except (TypeError, ValueError):
            accepts_icons = True
        try:
            if accepts_icons:
                callback(descriptions, current_values, error, icon_result)
            else:
                callback(descriptions, current_values, error)
        except RuntimeError:
            pass

    def refresh_state(self) -> None:
        threading.Thread(
            target=self._refresh_worker, args=(replace(self.profile),), daemon=True
        ).start()

    def _refresh_worker(self, profile: DatabaseProfile) -> None:
        try:
            latest = FeatureStateStore(profile).latest_runs()
            self._signals.state_ready.emit(latest, "")
        except Exception as exc:
            self._signals.state_ready.emit({}, str(exc))

    def _state_ready(self, latest, error: str) -> None:
        self.latest = latest
        self.connection_label.setText(
            f"连接失败 · {self.profile.name}" if error else f"已连接 · {self.profile.name}"
        )
        if self.cards_frame is not None:
            self._render_cards()

    def show_feature_details(self, feature: Feature) -> None:
        run = self.latest.get(feature.id)
        if run is None:
            content = f"{feature.title}\n\n尚无执行记录。\n\n{feature.description}"
        else:
            content = (
                f"功能：{feature.title}\n状态：{STATUS_STYLE.get(self._run_status(feature), (run.status, '', ''))[0]}\n"
                f"记录版本：{run.feature_version}\n当前版本：{self.feature_version(feature)}\n"
                f"开始：{run.started_at}\n结束：{run.finished_at}\n耗时：{run.duration_ms or 0} ms\n\n"
                f"错误：{run.error_message or '无'}\n\n日志：\n{run.log_excerpt or '（无日志）'}"
            )
        self._text_dialog(f"记录详情 · {feature.title}", content)

    def show_result_log(self, result: RunResult) -> None:
        self._text_dialog(f"执行日志 · {result.feature.title}", result.output or "（无输出）")

    def _text_dialog(self, title: str, content: str) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(900, 620)
        layout = QVBoxLayout(dialog)
        text = QPlainTextEdit(content)
        text.setReadOnly(True)
        text.setStyleSheet("background:#101923;color:#D8E5ED;font-family:monospace")
        layout.addWidget(text)
        close_button = QPushButton("关闭")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button, 0, Qt.AlignRight)
        dialog.exec_()

    def show_history(self) -> None:
        self._clear_main()
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        header = QHBoxLayout()
        title = QLabel("执行历史")
        title.setObjectName("pageTitle")
        refresh = QPushButton("刷新")
        refresh.setObjectName("primaryButton")
        refresh.clicked.connect(self.show_history)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(refresh)
        layout.addLayout(header)
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(("执行时间", "功能", "状态", "代码版本", "耗时"))
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.verticalHeader().setVisible(False)
        layout.addWidget(table, 1)
        self.main_layout.addWidget(page)
        try:
            runs = FeatureStateStore(self.profile).history()
            table.setRowCount(len(runs))
            for row, run in enumerate(runs):
                status = STATUS_STYLE.get(run.status, (run.status, "", ""))[0]
                values = (run.started_at, run.feature_title, status, run.feature_version, f"{run.duration_ms or 0} ms")
                for column, value in enumerate(values):
                    table.setItem(row, column, QTableWidgetItem(str(value)))
                table.item(row, 0).setData(Qt.UserRole, run)
            header_view = table.horizontalHeader()
            header_view.setSectionResizeMode(0, QHeaderView.ResizeToContents)
            header_view.setSectionResizeMode(1, QHeaderView.Stretch)
            for column in (2, 3, 4):
                header_view.setSectionResizeMode(column, QHeaderView.ResizeToContents)

            def open_log(index) -> None:
                item = table.item(index.row(), 0)
                run = item.data(Qt.UserRole)
                self._text_dialog(
                    f"历史日志 · {run.feature_title}",
                    run.log_excerpt or run.error_message or "（无日志）",
                )

            table.doubleClicked.connect(open_log)
        except Exception as exc:
            _message_error(self, "无法读取历史", str(exc))

    def apply_settings(self, settings: AppSettings, refresh: bool = True) -> None:
        if not settings.profiles:
            raise ValueError("至少需要一个数据库连接。")
        settings.selected_profile = min(
            max(settings.selected_profile, 0), len(settings.profiles) - 1
        )
        save_settings(settings)
        self.settings = settings
        self._reload_profile_widgets(refresh=refresh)

    def save_dialog_geometry(self, key: str, geometry: str) -> None:
        geometries = dict(self.settings.dialog_geometries)
        if geometries.get(key) == geometry:
            return
        geometries[key] = geometry
        updated = replace(self.settings, dialog_geometries=geometries)
        save_settings(updated)
        self.settings = updated

    def save_and_reload_profiles(self, refresh: bool = True) -> None:
        self.apply_settings(self.settings, refresh=refresh)

    def _reload_profile_widgets(self, refresh: bool = True) -> None:
        names = [profile.name for profile in self.settings.profiles]
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItems(names)
        self.profile_combo.setCurrentIndex(self.settings.selected_profile)
        self.profile_combo.blockSignals(False)
        self.latest = {}
        self.connection_label.setText(f"尚未连接 · {self.profile.name}")
        if refresh:
            self.show_features()
            self.refresh_state()

    def _profile_changed(self, index: int) -> None:
        if index < 0 or index >= len(self.settings.profiles):
            return
        self.settings.selected_profile = index
        save_settings(self.settings)
        self.latest = {}
        self.show_features()
        self.refresh_state()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.settings.window_geometry = _geometry_string(self)
        save_settings(self.settings)
        super().closeEvent(event)


def launch() -> None:
    application = QApplication.instance() or QApplication(sys.argv)
    application.setApplicationName("Azeroth DB Forge")
    window = DbToolApp()
    window.show()
    raise SystemExit(application.exec_())
