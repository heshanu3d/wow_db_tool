from __future__ import annotations

import copy
import importlib
import inspect
import queue
import threading
import tkinter as tk
from dataclasses import replace
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from PIL import Image, ImageTk

from .config import AppSettings, DatabaseProfile, load_settings, save_settings
from .features import (
    CATEGORIES,
    CUSTOM_SKILL_CONDITIONS_KEY,
    FEATURE_BY_ID,
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

SKILL_COLUMN_MIN_SIZES = (48, 48, 92, 150, 126, 60)
CUSTOM_SKILLS_DIALOG_GEOMETRY_KEY = "custom_skills_manager"
CUSTOM_SKILL_EDITOR_GEOMETRY_KEY = "custom_skill_editor"


def _load_tk_icon(path: str | Path, size: int = 34):
    """Load one cached PNG as a Tk image; malformed cache files stay non-fatal."""
    try:
        with Image.open(path) as image:
            converted = image.convert("RGBA")
            converted.thumbnail((size, size), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(converted)
    except (OSError, ValueError, tk.TclError):
        return None


def _restore_dialog_geometry(
    dialog: tk.Toplevel, settings: AppSettings, key: str, default: str
) -> None:
    """Restore a saved dialog size/position, falling back if it is invalid."""
    geometry = settings.dialog_geometries.get(key, default)
    try:
        dialog.geometry(geometry)
    except tk.TclError:
        dialog.geometry(default)


STATUS_STYLE = {
    "none": ("未应用", COLORS["muted"], COLORS["slate_soft"]),
    "applied": ("已应用", COLORS["teal"], COLORS["teal_soft"]),
    "marked": ("已标记", COLORS["teal"], COLORS["teal_soft"]),
    "updated": ("代码/配置有更新", "#946314", COLORS["gold_soft"]),
    "failed": ("执行失败", COLORS["red"], COLORS["red_soft"]),
    "running": ("执行中", COLORS["navy_2"], COLORS["blue_soft"]),
}


class ScrollFrame(tk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.canvas = tk.Canvas(self, highlightthickness=0, bg=COLORS["paper"])
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=COLORS["paper"])
        self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.inner.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.window_id, width=e.width))
        self._register_mousewheel_dispatcher()

    def _register_mousewheel_dispatcher(self):
        # One root-level dispatcher supports nested dialogs without allowing a
        # newly-created ScrollFrame to overwrite an older page's wheel binding.
        root = self._root()
        registry = getattr(root, "_db_tool_scroll_frames", None)
        if registry is None:
            registry = []
            root._db_tool_scroll_frames = registry
            root.bind_all(
                "<MouseWheel>",
                lambda event, owner=root: ScrollFrame._dispatch_mousewheel(owner, event),
            )
            root.bind_all(
                "<Button-4>",
                lambda event, owner=root: ScrollFrame._dispatch_mousewheel(owner, event),
            )
            root.bind_all(
                "<Button-5>",
                lambda event, owner=root: ScrollFrame._dispatch_mousewheel(owner, event),
            )
        registry.append(self)

    @staticmethod
    def _dispatch_mousewheel(root, event):
        registry = getattr(root, "_db_tool_scroll_frames", [])
        live = []
        for frame in registry:
            try:
                if frame.winfo_exists():
                    live.append(frame)
            except tk.TclError:
                pass
        root._db_tool_scroll_frames = live
        try:
            current = root.winfo_containing(event.x_root, event.y_root)
        except tk.TclError:
            return None
        live_set = set(live)
        while current is not None:
            if current in live_set:
                return current._scroll_event(event)
            current = getattr(current, "master", None)
        return None

    @staticmethod
    def _wheel_units(event):
        if getattr(event, "num", None) == 4:
            return -1
        if getattr(event, "num", None) == 5:
            return 1
        delta = getattr(event, "delta", 0)
        if not delta:
            return None
        units = int(-delta / 120)
        return units or (-1 if delta > 0 else 1)

    def _scroll_event(self, event):
        units = self._wheel_units(event)
        if units is None:
            return None
        try:
            self.canvas.yview_scroll(units, "units")
            return "break"
        except tk.TclError:
            return None

    def _mousewheel(self, event):
        """Direct handler retained for tests and programmatic wheel forwarding."""
        try:
            if not self.winfo_exists():
                return None
            target = self.winfo_containing(event.x_root, event.y_root)
            current = target
            while current is not None and current is not self:
                current = getattr(current, "master", None)
            if current is not self:
                return None
            return self._scroll_event(event)
        except tk.TclError:
            return None


class ProfilesDialog(tk.Toplevel):
    def __init__(self, master: "DbToolApp"):
        super().__init__(master)
        self.app = master
        self.title("数据库连接配置")
        self.geometry("780x560")
        self.minsize(720, 520)
        self.configure(bg=COLORS["paper"])
        self.transient(master)
        self.grab_set()
        self.profiles = [replace(p) for p in master.settings.profiles]
        self.current = min(max(0, master.settings.selected_profile), len(self.profiles) - 1)
        # Track the profile actually displayed by the form separately from the
        # Listbox selection. Tk may deliver selection events after focus changes;
        # using only ``current`` could then write edited fields to the wrong row.
        self.form_profile_index = self.current
        self.vars = {
            "name": tk.StringVar(), "host": tk.StringVar(), "port": tk.StringVar(),
            "user": tk.StringVar(), "password": tk.StringVar(), "database": tk.StringVar(),
            "auth_plugin": tk.StringVar(),
        }
        self._build()
        self._refresh_list()
        self.listbox.selection_set(self.current)
        self._load_current()

    def _build(self):
        header = tk.Frame(self, bg=COLORS["navy"], height=70)
        header.grid(row=0, column=0, sticky="ew")
        header.pack_propagate(False)
        tk.Label(header, text="数据库目标", font=("Noto Sans CJK SC", 18, "bold"), fg="white", bg=COLORS["navy"]).pack(anchor="w", padx=24, pady=(13, 0))
        tk.Label(header, text="执行状态会记录在所选数据库中", font=("Noto Sans CJK SC", 9), fg="#C7D3E0", bg=COLORS["navy"]).pack(anchor="w", padx=24)

        body = tk.Frame(self, bg=COLORS["paper"])
        left = tk.Frame(body, bg=COLORS["surface"], highlightbackground=COLORS["line"], highlightthickness=1)
        left.pack(side="left", fill="y", ipadx=8, ipady=8)
        self.listbox = tk.Listbox(
            left, width=23, height=12, relief="flat", borderwidth=0,
            font=("Noto Sans CJK SC", 10), selectbackground=COLORS["navy_2"],
            activestyle="none", exportselection=False,
        )
        self.listbox.pack(fill="both", expand=True, padx=8, pady=8)
        self.listbox.bind("<<ListboxSelect>>", self._select_profile)
        row = tk.Frame(left, bg=COLORS["surface"])
        row.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(row, text="新增", command=self._add).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="删除", command=self._delete).pack(side="left", fill="x", expand=True, padx=(6, 0))

        form = tk.Frame(body, bg=COLORS["surface"], highlightbackground=COLORS["line"], highlightthickness=1)
        form.pack(side="left", fill="both", expand=True, padx=(18, 0))
        fields = [
            ("连接名称", "name", False), ("主机地址", "host", False), ("端口", "port", False),
            ("用户名", "user", False), ("密码", "password", True), ("数据库", "database", False),
            ("认证插件", "auth_plugin", False),
        ]
        for i, (label, key, secret) in enumerate(fields):
            tk.Label(form, text=label, bg=COLORS["surface"], fg=COLORS["ink"], font=("Noto Sans CJK SC", 9, "bold")).grid(row=i, column=0, sticky="w", padx=(22, 12), pady=7)
            entry = ttk.Entry(form, textvariable=self.vars[key], show="•" if secret else "")
            entry.grid(row=i, column=1, sticky="ew", padx=(0, 22), pady=7)
        form.columnconfigure(1, weight=1)

        actions = tk.Frame(self, bg=COLORS["paper"])
        actions.grid(row=2, column=0, sticky="ew", padx=22, pady=(0, 16))
        ttk.Button(actions, text="取消", command=self.destroy).pack(side="right")
        ttk.Button(actions, text="保存连接", style="Accent.TButton", command=self._save).pack(side="right", padx=(0, 10))
        ttk.Button(actions, text="测试当前连接", command=self._test).pack(side="left")

        body.grid(row=1, column=0, sticky="nsew", padx=22, pady=(16, 12))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

    def _commit_fields(self, validate: bool = False):
        if not self.profiles:
            return
        raw_port = self.vars["port"].get().strip()
        try:
            port = int(raw_port or 3306)
        except ValueError:
            if validate:
                raise ValueError("端口必须是 1 到 65535 之间的整数。")
            port = self.profiles[self.form_profile_index].port
        if not 1 <= port <= 65535:
            if validate:
                raise ValueError("端口必须是 1 到 65535 之间的整数。")
            port = self.profiles[self.form_profile_index].port
        self.profiles[self.form_profile_index] = DatabaseProfile(
            self.vars["name"].get().strip() or "未命名连接",
            self.vars["host"].get().strip(), port,
            self.vars["user"].get().strip(), self.vars["password"].get(),
            self.vars["database"].get().strip(), self.vars["auth_plugin"].get().strip(),
        )

    def _load_current(self):
        if not self.profiles:
            return
        self.form_profile_index = self.current
        p = self.profiles[self.form_profile_index]
        for key in self.vars:
            self.vars[key].set(str(getattr(p, key)))

    def _refresh_list(self):
        self.listbox.delete(0, "end")
        for profile in self.profiles:
            self.listbox.insert("end", profile.name)

    def _select_profile(self, _event=None):
        selected = self.listbox.curselection()
        if not selected:
            return
        self._commit_fields()
        self.current = selected[0]
        self._load_current()

    def _add(self):
        self._commit_fields()
        self.profiles.append(DatabaseProfile(name="新连接"))
        self.current = len(self.profiles) - 1
        self._refresh_list()
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(self.current)
        self._load_current()

    def _delete(self):
        if len(self.profiles) <= 1:
            messagebox.showinfo("保留连接", "至少保留一个数据库连接。", parent=self)
            return
        del self.profiles[self.current]
        self.current = min(self.current, len(self.profiles) - 1)
        self._refresh_list()
        self.listbox.selection_set(self.current)
        self._load_current()

    def _test(self):
        self._commit_fields()
        profile = self.profiles[self.form_profile_index]
        self.config(cursor="watch")
        self.update_idletasks()
        try:
            version = FeatureStateStore(profile).test_connection()
            messagebox.showinfo("连接成功", f"已连接 {profile.target_label}\nMySQL {version}", parent=self)
        except Exception as exc:
            messagebox.showerror("连接失败", f"{profile.target_label}\n\n{exc}", parent=self)
        finally:
            self.config(cursor="")

    def _save(self):
        try:
            self._commit_fields(validate=True)
            updated = AppSettings(
                profiles=[replace(profile) for profile in self.profiles],
                selected_profile=self.form_profile_index,
                window_geometry=self.app.settings.window_geometry,
                dialog_geometries=copy.deepcopy(self.app.settings.dialog_geometries),
                feature_configs=copy.deepcopy(self.app.settings.feature_configs),
                spell_icon_dbc_path=self.app.settings.spell_icon_dbc_path,
                spell_icon_client_root=self.app.settings.spell_icon_client_root,
            )
            # Persist first. The dialog remains open and reports an actionable
            # error if the file cannot be written; it is no longer closed after
            # a failed save.
            self.app.apply_settings(updated)
        except (OSError, ValueError, TypeError) as exc:
            messagebox.showerror("保存连接失败", str(exc), parent=self)
            return
        self.destroy()


class IconResourcesDialog(tk.Toplevel):
    """Configure extracted WoW client resources used to render spell icons."""

    def __init__(self, app: "DbToolApp", parent=None):
        super().__init__(parent or app)
        self.app = app
        self.title("技能图标资源")
        self.geometry("760x330")
        self.minsize(680, 300)
        self.configure(bg=COLORS["paper"])
        self.transient(parent or app)
        self.grab_set()
        suggested_dbc, suggested_root = suggested_spell_icon_paths()
        self.dbc_var = tk.StringVar(
            self, value=app.settings.spell_icon_dbc_path or suggested_dbc
        )
        self.root_var = tk.StringVar(
            self, value=app.settings.spell_icon_client_root or suggested_root
        )
        self._build()

    def _build(self):
        content = tk.Frame(self, bg=COLORS["paper"])
        content.pack(fill="both", expand=True, padx=24, pady=20)
        tk.Label(
            content, text="技能图标资源", bg=COLORS["paper"], fg=COLORS["ink"],
            font=("Noto Sans CJK SC", 17, "bold"),
        ).pack(anchor="w")
        tk.Label(
            content,
            text=("需要从 WoW 3.3.5a 客户端解压 SpellIcon.dbc，以及 "
                  "Interface/Icons/*.blp 或 Interface/Spellbook/*.blp。"
                  "图标会转换成 PNG 并缓存在项目目录中。"),
            bg=COLORS["paper"], fg=COLORS["muted"], justify="left",
            wraplength=700, font=("Noto Sans CJK SC", 9),
        ).pack(anchor="w", pady=(4, 16))

        form = tk.Frame(
            content, bg=COLORS["surface"], highlightbackground=COLORS["line"],
            highlightthickness=1,
        )
        form.pack(fill="both", expand=True)
        form.grid_columnconfigure(1, weight=1)
        rows = (
            ("SpellIcon.dbc", self.dbc_var, self._choose_dbc),
            ("客户端解压根目录", self.root_var, self._choose_root),
        )
        for row, (label, variable, command) in enumerate(rows):
            tk.Label(
                form, text=label, bg=COLORS["surface"], fg=COLORS["ink"],
                font=("Noto Sans CJK SC", 9, "bold"),
            ).grid(row=row, column=0, sticky="w", padx=(18, 12), pady=(18 if row == 0 else 10, 10))
            ttk.Entry(form, textvariable=variable).grid(
                row=row, column=1, sticky="ew", pady=(18 if row == 0 else 10, 10)
            )
            ttk.Button(form, text="浏览…", command=command).grid(
                row=row, column=2, padx=(10, 18), pady=(18 if row == 0 else 10, 10)
            )
        tk.Label(
            form,
            text=("根目录下应存在 Interface/Icons 或 Interface/Spellbook；也可直接选择 "
                  "Icons/Spellbook 目录。清空两个路径可停用图标同步，但已缓存图标仍可显示。"),
            bg=COLORS["surface"], fg=COLORS["muted"], justify="left",
            wraplength=650, font=("Noto Sans CJK SC", 8),
        ).grid(row=2, column=0, columnspan=3, sticky="w", padx=18, pady=(0, 14))

        actions = tk.Frame(content, bg=COLORS["paper"])
        actions.pack(fill="x", pady=(14, 0))
        ttk.Button(actions, text="取消", command=self.destroy).pack(side="right")
        ttk.Button(
            actions, text="保存并刷新", style="Accent.TButton", command=self._save
        ).pack(side="right", padx=(0, 8))

    def _choose_dbc(self):
        value = filedialog.askopenfilename(
            parent=self, title="选择 SpellIcon.dbc",
            filetypes=(("DBC 文件", "*.dbc"), ("所有文件", "*")),
        )
        if value:
            self.dbc_var.set(value)

    def _choose_root(self):
        value = filedialog.askdirectory(parent=self, title="选择客户端解压根目录")
        if value:
            self.root_var.set(value)

    def _save(self):
        dbc = self.dbc_var.get().strip()
        root = self.root_var.get().strip()
        try:
            if bool(dbc) != bool(root):
                raise ValueError("SpellIcon.dbc 和客户端解压根目录需要同时填写，或同时清空。")
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
            messagebox.showerror("图标资源配置无效", str(exc), parent=self)
            return
        self.destroy()


class CustomSkillEditorDialog(tk.Toplevel):
    """Add or edit one GUI-defined spell condition and modification."""

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
        self.title("编辑自定义技能" if original_skill else "新增自定义技能")
        self.minsize(680, 680)
        _restore_dialog_geometry(
            self, self.view.app.settings, CUSTOM_SKILL_EDITOR_GEOMETRY_KEY,
            "780x740",
        )
        self.configure(bg=COLORS["paper"])
        self.transient(manager)
        self.protocol("WM_DELETE_WINDOW", self._close)

        current = {}
        if original_group and original_skill:
            current = self.view.configuration[original_group][original_skill]
        initial_group = original_group or self.view.active_group.config_name
        self.group_var = tk.StringVar(self, value=self._group_title(initial_group))
        self.skill_var = tk.StringVar(self, value=original_skill or "")
        self.value_var = tk.StringVar(self, value=str(current.get("value", "")))
        self.enabled_var = tk.BooleanVar(self, value=bool(current.get("enabled", True)))
        self.template_var = tk.StringVar(
            self, value=SKILL_CONDITION_TEMPLATES[0].title
        )
        self.template_help_var = tk.StringVar(
            self, value=SKILL_CONDITION_TEMPLATES[0].description
        )
        self.preview_var = tk.StringVar(
            self, value="填写 WHERE 后的判断表达式，然后点击“测试查询”。"
        )
        self._build()
        self._render_preview()
        if original_skill:
            self.condition_text.insert(
                "1.0", self.view.custom_conditions.get(original_skill, "")
            )
        # A double-click binding runs during ButtonPress handling. Tk cannot
        # grab a newly created Toplevel until the window manager has mapped it,
        # which previously raised "grab failed: window not viewable" before
        # the form was built. Wait for visibility before making it modal.
        self.wait_visibility()
        self.grab_set()
        self.skill_entry.focus_set()

    def _group_title(self, group_name: str) -> str:
        group = next(
            item for item in self.view.feature.config_groups
            if item.config_name == group_name
        )
        return group.title

    def _selected_group_name(self) -> str:
        title = self.group_var.get()
        group = next(
            (item for item in self.view.feature.config_groups if item.title == title),
            None,
        )
        if group is None:
            raise ValueError("请选择有效的技能修改类型。")
        return group.config_name

    def _build(self):
        content = tk.Frame(self, bg=COLORS["paper"])
        content.pack(fill="both", expand=True, padx=24, pady=20)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(2, weight=1)
        tk.Label(
            content, text="自定义职业技能", bg=COLORS["paper"], fg=COLORS["ink"],
            font=("Noto Sans CJK SC", 17, "bold"),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            content,
            text="查询条件会同时用于读取当前值、技能描述以及真正执行数据库修改。",
            bg=COLORS["paper"], fg=COLORS["muted"],
            font=("Noto Sans CJK SC", 9),
        ).grid(row=1, column=0, sticky="w", pady=(4, 16))

        form = tk.Frame(
            content, bg=COLORS["surface"], highlightbackground=COLORS["line"],
            highlightthickness=1,
        )
        form.grid(row=2, column=0, sticky="nsew")
        form.grid_columnconfigure(1, weight=1)
        form.grid_rowconfigure(5, weight=3)
        form.grid_rowconfigure(7, weight=2)

        labels = ("修改类型", "技能定义名称", "修改值")
        for row, text in enumerate(labels):
            tk.Label(
                form, text=text, bg=COLORS["surface"], fg=COLORS["ink"],
                anchor="e", font=("Noto Sans CJK SC", 9, "bold"),
            ).grid(row=row, column=0, sticky="e", padx=(18, 12), pady=(16 if row == 0 else 8, 8))

        self.group_box = ttk.Combobox(
            form, textvariable=self.group_var, state="readonly",
            values=[group.title for group in self.view.feature.config_groups],
        )
        self.group_box.grid(row=0, column=1, sticky="ew", padx=(0, 18), pady=(16, 8))
        self.skill_entry = ttk.Entry(form, textvariable=self.skill_var)
        self.skill_entry.grid(row=1, column=1, sticky="ew", padx=(0, 18), pady=8)
        value_line = tk.Frame(form, bg=COLORS["surface"])
        value_line.grid(row=2, column=1, sticky="ew", padx=(0, 18), pady=8)
        ttk.Entry(value_line, textvariable=self.value_var, width=22).pack(side="left")
        tk.Checkbutton(
            value_line, text="新增后启用", variable=self.enabled_var,
            bg=COLORS["surface"], activebackground=COLORS["surface"],
            highlightthickness=0,
        ).pack(side="left", padx=(18, 0))

        tk.Label(
            form, text="查询模板", bg=COLORS["surface"], fg=COLORS["ink"],
            anchor="e", font=("Noto Sans CJK SC", 9, "bold"),
        ).grid(row=3, column=0, sticky="e", padx=(18, 12), pady=(8, 4))
        template_line = tk.Frame(form, bg=COLORS["surface"])
        template_line.grid(row=3, column=1, sticky="ew", padx=(0, 18), pady=(8, 4))
        self.template_box = ttk.Combobox(
            template_line, textvariable=self.template_var, state="readonly",
            values=[template.title for template in SKILL_CONDITION_TEMPLATES],
        )
        self.template_box.pack(side="left", fill="x", expand=True)
        self.template_box.bind("<<ComboboxSelected>>", self._template_selected)
        ttk.Button(
            template_line, text="套用模板", command=self._apply_condition_template
        ).pack(side="left", padx=(8, 0))
        tk.Label(
            form, textvariable=self.template_help_var, bg=COLORS["surface"],
            fg=COLORS["muted"], justify="left", anchor="w", wraplength=540,
            font=("Noto Sans CJK SC", 8),
        ).grid(row=4, column=1, sticky="ew", padx=(0, 18), pady=(0, 4))

        tk.Label(
            form, text="查询条件", bg=COLORS["surface"], fg=COLORS["ink"],
            anchor="ne", font=("Noto Sans CJK SC", 9, "bold"),
        ).grid(row=5, column=0, sticky="ne", padx=(18, 12), pady=(8, 8))
        condition_box = tk.Frame(form, bg=COLORS["surface"])
        condition_box.grid(row=5, column=1, sticky="nsew", padx=(0, 18), pady=(8, 8))
        self.condition_text = tk.Text(
            condition_box, height=6, wrap="word", undo=True,
            font=("DejaVu Sans Mono", 9), relief="solid", borderwidth=1,
        )
        condition_scroll = ttk.Scrollbar(
            condition_box, orient="vertical", command=self.condition_text.yview
        )
        self.condition_text.configure(yscrollcommand=condition_scroll.set)
        self.condition_text.pack(side="left", fill="both", expand=True)
        condition_scroll.pack(side="right", fill="y")

        tk.Label(
            form,
            text="示例：s.SpellName4='死亡之握' and s.ID=49576\n"
                 "只填写 WHERE 后面的条件；不能包含分号、SQL 注释、SELECT 或修改数据库的语句。",
            bg=COLORS["surface"], fg=COLORS["muted"], justify="left",
            font=("Noto Sans CJK SC", 8),
        ).grid(row=6, column=1, sticky="w", padx=(0, 18), pady=(0, 8))

        preview_box = tk.Frame(form, bg=COLORS["blue_soft"])
        preview_box.grid(
            row=7, column=0, columnspan=2, sticky="nsew", padx=18, pady=(4, 14)
        )
        self.preview_text = tk.Text(
            preview_box, height=5, wrap="word", relief="flat", borderwidth=0,
            bg=COLORS["blue_soft"], fg=COLORS["navy_2"],
            font=("Noto Sans CJK SC", 8), padx=10, pady=8, state="disabled",
        )
        preview_scroll = ttk.Scrollbar(
            preview_box, orient="vertical", command=self.preview_text.yview
        )
        self.preview_text.configure(yscrollcommand=preview_scroll.set)
        self.preview_text.pack(side="left", fill="both", expand=True)
        preview_scroll.pack(side="right", fill="y")

        actions = tk.Frame(content, bg=COLORS["paper"])
        actions.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        ttk.Button(actions, text="取消", command=self._close).pack(side="right")
        ttk.Button(
            actions, text="保存并查询", style="Accent.TButton", command=self._save
        ).pack(side="right", padx=(0, 8))
        ttk.Button(actions, text="测试查询", command=self._test_query).pack(side="left")

    def _selected_condition_template(self):
        template = SKILL_CONDITION_TEMPLATE_BY_TITLE.get(self.template_var.get())
        if template is None:
            template = SKILL_CONDITION_TEMPLATES[0]
            self.template_var.set(template.title)
        return template

    def _template_selected(self, _event=None) -> None:
        self.template_help_var.set(self._selected_condition_template().description)

    def _apply_condition_template(self) -> None:
        template = self._selected_condition_template()
        self.template_help_var.set(template.description)
        self.condition_text.delete("1.0", "end")
        self.condition_text.insert("1.0", template.render(self.skill_var.get()))
        self.condition_text.focus_set()

    def _render_preview(self) -> None:
        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", "end")
        self.preview_text.insert("1.0", self.preview_var.get())
        self.preview_text.configure(state="disabled")

    def _close(self) -> None:
        self.update_idletasks()
        self.view.app.save_dialog_geometry(
            CUSTOM_SKILL_EDITOR_GEOMETRY_KEY, self.geometry()
        )
        self.destroy()

    def _values(self) -> tuple[str, str, str, str, bool]:
        group_name = self._selected_group_name()
        skill = self.skill_var.get().strip()
        value = self.value_var.get().strip()
        condition = validate_skill_condition(self.condition_text.get("1.0", "end"))
        if not skill:
            raise ValueError("技能定义名称不能为空。")
        if len(skill) > 80:
            raise ValueError("技能定义名称不能超过 80 个字符。")
        self.view.feature.validate_custom_skill_value(group_name, skill, value)
        return group_name, skill, value, condition, self.enabled_var.get()

    def _test_query(self):
        try:
            condition = validate_skill_condition(
                self.condition_text.get("1.0", "end")
            )
            self.config(cursor="watch")
            self.update_idletasks()
            preview = preview_skill_condition(self.view.app.profile, condition)
        except Exception as exc:
            messagebox.showerror("测试查询失败", str(exc), parent=self)
            return
        finally:
            self.config(cursor="")
        lines = [f"匹配 {preview.count} 条 spell 记录（最多显示 20 条）："]
        if preview.rows:
            lines.extend(
                f"ID {row.get('spell_id')} · {row.get('spell_name') or '未命名'}"
                f" · {row.get('spell_rank') or '无等级'}"
                for row in preview.rows
            )
        else:
            lines.append("没有匹配结果，请检查条件或当前数据库版本。")
        self.preview_var.set("\n".join(lines))
        self._render_preview()

    def _save(self):
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
            messagebox.showerror("自定义技能无效", str(exc), parent=self)
            return
        self.manager.refresh_rows()
        self._close()


class CustomSkillsDialog(tk.Toplevel):
    """Manage all GUI-defined skills for one class feature."""

    COLUMN_MIN_SIZES = (170, 52, 130, 55, 90, 120)

    def __init__(self, view: "SkillConfigView"):
        super().__init__(view)
        self.view = view
        self.title(f"{view.feature.title} · 管理自定义技能")
        self.minsize(760, 480)
        _restore_dialog_geometry(
            self, self.view.app.settings, CUSTOM_SKILLS_DIALOG_GEOMETRY_KEY,
            "980x560",
        )
        self.configure(bg=COLORS["paper"])
        self.transient(view.winfo_toplevel())
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.grab_set()
        self.row_keys: dict[str, tuple[str, str]] = {}
        self.row_frames: dict[tuple[str, str], tk.Frame] = {}
        self.icon_labels: dict[tuple[str, str], tk.Label] = {}
        self.selected_key: tuple[str, str] | None = None
        self.icon_images: dict[str, object] = {}
        self._build()
        add_listener = getattr(self.view, "add_icon_listener", None)
        if add_listener:
            add_listener(self._icons_updated)
        self.refresh_rows()

    @classmethod
    def _configure_columns(cls, frame: tk.Frame):
        for column, minsize in enumerate(cls.COLUMN_MIN_SIZES):
            frame.grid_columnconfigure(
                column, minsize=minsize, weight=1 if column == 5 else 0
            )

    def _build(self):
        content = tk.Frame(self, bg=COLORS["paper"])
        content.pack(fill="both", expand=True, padx=22, pady=18)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(3, weight=1)
        tk.Label(
            content, text="管理自定义技能", bg=COLORS["paper"], fg=COLORS["ink"],
            font=("Noto Sans CJK SC", 17, "bold"),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            content,
            text="这里新增的技能会参与图标、当前值、描述查询和实际应用；完成后请回到技能配置页点击“保存配置”。",
            bg=COLORS["paper"], fg=COLORS["muted"],
            font=("Noto Sans CJK SC", 9),
        ).grid(row=1, column=0, sticky="w", pady=(4, 14))

        headings = tk.Frame(content, bg=COLORS["slate_soft"])
        headings.grid(row=2, column=0, sticky="ew")
        self._configure_columns(headings)
        for column, text in enumerate(
            ("修改类型", "图标", "技能定义", "启用", "修改值", "查询条件")
        ):
            tk.Label(
                headings, text=text,
                anchor="center" if column in (1, 3) else "w",
                bg=COLORS["slate_soft"], fg=COLORS["muted"],
                font=("Noto Sans CJK SC", 8, "bold"),
            ).grid(row=0, column=column, sticky="ew", padx=8, pady=7)

        self.rows = ScrollFrame(content, bg=COLORS["surface"])
        self.rows.grid(row=3, column=0, sticky="nsew")

        actions = tk.Frame(content, bg=COLORS["paper"])
        actions.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        ttk.Button(actions, text="新增技能", style="Accent.TButton", command=self._add).pack(side="left")
        ttk.Button(actions, text="编辑", command=self._edit).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="删除", command=self._delete).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="图标资源", command=self._configure_icons).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="关闭", command=self._close).pack(side="right")

    def _close(self) -> None:
        remove_listener = getattr(self.view, "remove_icon_listener", None)
        if remove_listener:
            remove_listener(self._icons_updated)
        self.update_idletasks()
        self.view.app.save_dialog_geometry(
            CUSTOM_SKILLS_DIALOG_GEOMETRY_KEY, self.geometry()
        )
        self.destroy()

    def _configure_icons(self):
        IconResourcesDialog(self.view.app, self)

    def _bind_row(self, widget: tk.Widget, key: tuple[str, str]):
        widget.bind("<Button-1>", lambda _event, item=key: self._select(item), add="+")
        widget.bind("<Double-1>", lambda _event, item=key: self._edit(item), add="+")
        for child in widget.winfo_children():
            self._bind_row(child, key)

    def _select(self, key: tuple[str, str]):
        self.selected_key = key
        for row_key, frame in self.row_frames.items():
            background = COLORS["blue_soft"] if row_key == key else frame._normal_bg
            frame.configure(bg=background)
            for child in frame.winfo_children():
                try:
                    child.configure(bg=background)
                except tk.TclError:
                    pass

    def refresh_rows(self):
        selected = self.selected_key
        self.row_keys.clear()
        self.row_frames.clear()
        self.icon_labels.clear()
        self.icon_images.clear()
        for child in self.rows.inner.winfo_children():
            child.destroy()
        for index, row_data in enumerate(self.view.custom_skill_rows()):
            group_name, group_title, skill, enabled, value, condition = row_data
            key = (group_name, skill)
            item_id = f"custom-{index}"
            self.row_keys[item_id] = key
            row_bg = COLORS["surface"] if index % 2 == 0 else "#F8FAFC"
            row = tk.Frame(self.rows.inner, bg=row_bg)
            row._normal_bg = row_bg
            row.pack(fill="x")
            self._configure_columns(row)
            self.row_frames[key] = row
            values = (group_title, skill, "是" if enabled else "否", value, condition)
            tk.Label(
                row, text=values[0], anchor="w", bg=row_bg, fg=COLORS["ink"],
                font=("Noto Sans CJK SC", 9),
            ).grid(row=0, column=0, sticky="ew", padx=8, pady=8)
            image = None
            image_getter = getattr(self.view, "skill_icon_image", None)
            if image_getter:
                image = image_getter(skill, 30)
            if image is not None:
                self.icon_images[skill] = image
            icon_label = tk.Label(
                row, image=image, text="—" if image is None else "",
                anchor="center", bg=row_bg, fg=COLORS["muted"],
            )
            icon_label.grid(row=0, column=1, sticky="ew", padx=6, pady=4)
            self.icon_labels[key] = icon_label
            for column, value_text in enumerate(values[1:], start=2):
                tk.Label(
                    row, text=value_text, anchor="center" if column == 3 else "w",
                    justify="left", wraplength=360 if column == 5 else 125,
                    bg=row_bg, fg=COLORS["ink"] if column != 5 else COLORS["muted"],
                    font=("Noto Sans CJK SC", 9 if column < 5 else 8),
                ).grid(row=0, column=column, sticky="ew", padx=8, pady=8)
            self._bind_row(row, key)
        if selected in self.row_frames:
            self._select(selected)
        elif selected is not None:
            self.selected_key = None

    def _icons_updated(self, changed=None):
        if not changed:
            return
        try:
            if not self.winfo_exists():
                return
            for key, label in self.icon_labels.items():
                skill = key[1]
                if skill not in changed:
                    continue
                image = self.view.skill_icon_image(skill, 30)
                if image is None:
                    self.icon_images.pop(skill, None)
                else:
                    self.icon_images[skill] = image
                label.configure(image=image or "", text="—" if image is None else "")
                label._spell_icon_image = image
        except tk.TclError:
            pass

    def _selected(self) -> tuple[str, str] | None:
        return self.selected_key

    def _add(self):
        CustomSkillEditorDialog(self)

    def _edit(self, selected=None):
        selected = selected if isinstance(selected, tuple) else self._selected()
        if selected is None:
            messagebox.showinfo("请选择技能", "请先选择需要编辑的自定义技能。", parent=self)
            return
        CustomSkillEditorDialog(self, *selected)

    def _delete(self):
        selected = self._selected()
        if selected is None:
            messagebox.showinfo("请选择技能", "请先选择需要删除的自定义技能。", parent=self)
            return
        group_name, skill = selected
        if not messagebox.askyesno(
            "删除自定义技能", f"确定从此修改类型中删除“{skill}”吗？", parent=self
        ):
            return
        self.view.remove_custom_skill(group_name, skill)
        self.selected_key = None
        self.refresh_rows()


class SkillConfigView(tk.Frame):
    """Detailed per-skill editor for one class bundle."""

    def __init__(
        self,
        app: "DbToolApp",
        feature: Feature,
        navigation_state: dict | None = None,
    ):
        super().__init__(app.main, bg=COLORS["paper"])
        self.app = app
        self.feature = feature
        navigation_state = navigation_state or {}
        saved = navigation_state.get(
            "configuration", app.settings.feature_configs.get(feature.id, {})
        )
        normalized = feature.normalize_configuration(saved)
        self.custom_conditions = dict(
            normalized.pop(CUSTOM_SKILL_CONDITIONS_KEY, {})
        )
        self.configuration = normalized
        self.group_scroll_positions = dict(
            navigation_state.get("group_scroll_positions", {})
        )
        self.preserve_navigation_state = True
        self.enabled_vars: dict[tuple[str, str], tk.BooleanVar] = {}
        self.value_vars: dict[tuple[str, str], tk.StringVar] = {}
        self.current_value_vars: dict[tuple[str, str], tk.StringVar] = {}
        self.description_vars: dict[str, tk.StringVar] = {}
        self.icon_paths: dict[str, Path] = {}
        self.icon_images: dict[tuple[str, int, str], object] = {}
        self.icon_listeners: list[Callable] = []
        self.column_header_widgets: dict[int, tk.Widget] = {}
        self.row_column_widgets: dict[tuple[str, str], dict[int, tk.Widget]] = {}
        self.detail_request_id = 0
        self._initialize_variables()
        cached_loader = getattr(self.app, "cached_skill_icons", None)
        if cached_loader:
            self.icon_paths = cached_loader(self.feature, self._collect())
        active_group_name = navigation_state.get("active_group")
        self.active_group = next(
            (
                group
                for group in feature.config_groups
                if group.config_name == active_group_name
            ),
            feature.config_groups[0],
        )
        self.summary_var = tk.StringVar(self)
        self.description_status_var = tk.StringVar(
            self, value="正在从当前数据库读取技能当前值与描述"
        )
        self.icon_status_var = tk.StringVar(
            self,
            value=(
                f"图标：已加载缓存 {len(self.icon_paths)} 项，正在同步数据库"
                if self.icon_paths else "图标：正在同步数据库与本地缓存"
            ),
        )
        self.pack(fill="both", expand=True)
        self._build()
        self._render_group()
        self._update_summary()
        self._request_details()

    def _initialize_variables(self):
        for group in self.feature.config_groups:
            group_name = group.config_name
            for skill, item in self.configuration[group_name].items():
                key = (group_name, skill)
                self.enabled_vars[key] = tk.BooleanVar(
                    self, value=item["enabled"]
                )
                self.value_vars[key] = tk.StringVar(self, value=item["value"])
                self.current_value_vars[key] = tk.StringVar(
                    self, value="正在读取…"
                )
                if skill not in self.description_vars:
                    self.description_vars[skill] = tk.StringVar(
                        self, value="正在从当前数据库读取…"
                    )

    @staticmethod
    def _configure_skill_columns(frame: tk.Frame):
        for column, minsize in enumerate(SKILL_COLUMN_MIN_SIZES):
            frame.grid_columnconfigure(
                column, minsize=minsize, weight=1 if column == 5 else 0
            )

    def _build(self):
        header = tk.Frame(self, bg=COLORS["paper"])
        header.pack(fill="x", padx=28, pady=(22, 14))
        # Pack actions first so Tk reserves their full requested width at the
        # application's minimum size. The title area is the flexible region.
        header_actions = tk.Frame(header, bg=COLORS["paper"])
        header_actions.pack(side="right", anchor="s")
        ttk.Button(
            header_actions, text="图标资源", command=self._configure_icon_resources
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            header_actions, text="管理自定义技能", command=self._manage_custom_skills
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            header_actions, text="恢复代码默认值", command=self._reset_defaults
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            header_actions, text="保存配置", style="Accent.TButton", command=self._save
        ).pack(side="left")

        title_box = tk.Frame(header, bg=COLORS["paper"])
        title_box.pack(side="left", fill="x", expand=True)
        ttk.Button(
            title_box, text="← 返回职业技能", style="Quiet.TButton", command=self._back
        ).pack(anchor="w", pady=(0, 8))
        tk.Label(
            title_box, text=f"{self.feature.title} · 技能配置", bg=COLORS["paper"],
            fg=COLORS["ink"], font=("Noto Sans CJK SC", 21, "bold"),
        ).pack(anchor="w")
        tk.Label(
            title_box,
            text="勾选需要修改的技能，并填写目标数值或倍率。代码技能使用默认值，也可在 GUI 中添加自定义技能。",
            bg=COLORS["paper"], fg=COLORS["muted"], font=("Noto Sans CJK SC", 9),
        ).pack(anchor="w", pady=(4, 0))

        summary = tk.Frame(self, bg=COLORS["navy"], height=48)
        summary.pack(fill="x", padx=28, pady=(0, 14))
        summary.pack_propagate(False)
        tk.Label(
            summary, textvariable=self.summary_var, bg=COLORS["navy"], fg="white",
            font=("Noto Sans CJK SC", 10, "bold"),
        ).pack(side="left", padx=16)
        status_box = tk.Frame(summary, bg=COLORS["navy"])
        status_box.pack(side="right", padx=16)
        tk.Label(
            status_box, textvariable=self.description_status_var, bg=COLORS["navy"],
            fg="#B8C8D7", font=("Noto Sans CJK SC", 8), anchor="e",
        ).pack(anchor="e")
        tk.Label(
            status_box, textvariable=self.icon_status_var, bg=COLORS["navy"],
            fg="#9CC4D2", font=("Noto Sans CJK SC", 8), anchor="e",
        ).pack(anchor="e")

        body = tk.Frame(self, bg=COLORS["paper"])
        body.pack(fill="both", expand=True, padx=28, pady=(0, 22))
        nav = tk.Frame(
            body, bg=COLORS["surface"], width=235,
            highlightbackground=COLORS["line"], highlightthickness=1,
        )
        nav.pack(side="left", fill="y")
        nav.pack_propagate(False)
        tk.Label(
            nav, text="修改类型", bg=COLORS["surface"], fg=COLORS["muted"],
            font=("Noto Sans CJK SC", 9, "bold"),
        ).pack(anchor="w", padx=16, pady=(16, 8))
        self.group_list = tk.Listbox(
            nav, relief="flat", borderwidth=0, highlightthickness=0,
            exportselection=False, activestyle="none", selectbackground=COLORS["navy_2"],
            selectforeground="white", font=("Noto Sans CJK SC", 9),
        )
        self.group_list.pack(fill="both", expand=True, padx=8, pady=(0, 10))
        self._refresh_group_list()
        self.group_list.bind("<<ListboxSelect>>", self._group_selected)

        self.detail = ScrollFrame(body, bg=COLORS["paper"])
        self.detail.pack(side="left", fill="both", expand=True, padx=(16, 0))

    def _refresh_group_list(self):
        if not hasattr(self, "group_list"):
            return
        active_index = self.feature.config_groups.index(self.active_group) if hasattr(self, "active_group") else 0
        self.group_list.delete(0, "end")
        for group in self.feature.config_groups:
            count = len(self.configuration[group.config_name])
            self.group_list.insert("end", f"  {group.title}  ·  {count}")
        self.group_list.selection_set(active_index)
        self.group_list.see(active_index)

    def _group_selected(self, _event=None):
        selected = self.group_list.curselection()
        if not selected:
            return
        selected_group = self.feature.config_groups[selected[0]]
        if selected_group.config_name == self.active_group.config_name:
            return
        self._remember_active_group_scroll()
        self.active_group = selected_group
        self._render_group()

    def _remember_active_group_scroll(self):
        if not hasattr(self, "detail"):
            return
        try:
            position = self.detail.canvas.yview()[0]
        except tk.TclError:
            return
        self.group_scroll_positions[self.active_group.config_name] = position

    def _restore_group_scroll(self, group_name: str):
        try:
            if (
                not self.winfo_exists()
                or self.active_group.config_name != group_name
            ):
                return
            self.detail.inner.update_idletasks()
            self.detail.canvas.configure(
                scrollregion=self.detail.canvas.bbox("all")
            )
            self.detail.canvas.yview_moveto(
                self.group_scroll_positions.get(group_name, 0.0)
            )
        except tk.TclError:
            pass

    def navigation_state(self) -> dict:
        """Capture the unsaved editor state before another main page is shown."""
        self._remember_active_group_scroll()
        return {
            "configuration": self._collect(),
            "active_group": self.active_group.config_name,
            "group_scroll_positions": dict(self.group_scroll_positions),
        }

    def _render_group(self):
        parent = self.detail.inner
        for child in parent.winfo_children():
            child.destroy()
        self.row_column_widgets = {}

        section = tk.Frame(
            parent, bg=COLORS["surface"], highlightbackground=COLORS["line"],
            highlightthickness=1,
        )
        section.pack(fill="x")
        section_header = tk.Frame(section, bg=COLORS["surface"])
        section_header.pack(fill="x", padx=18, pady=(16, 12))
        title_box = tk.Frame(section_header, bg=COLORS["surface"])
        title_box.pack(side="left", fill="x", expand=True)
        tk.Label(
            title_box, text=self.active_group.title, bg=COLORS["surface"],
            fg=COLORS["ink"], font=("Noto Sans CJK SC", 14, "bold"),
        ).pack(anchor="w")
        if self.active_group.description:
            tk.Label(
                title_box, text=self.active_group.description, bg=COLORS["surface"],
                fg=COLORS["muted"], font=("Noto Sans CJK SC", 8),
            ).pack(anchor="w", pady=(3, 0))
        tools = tk.Frame(section_header, bg=COLORS["surface"])
        tools.pack(side="right")
        ttk.Button(
            tools, text="新增技能", style="Quiet.TButton",
            command=self._manage_custom_skills,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            tools, text="全选", style="Quiet.TButton",
            command=lambda: self._set_group_enabled(True),
        ).pack(side="left")
        ttk.Button(
            tools, text="全不选", style="Quiet.TButton",
            command=lambda: self._set_group_enabled(False),
        ).pack(side="left", padx=(6, 0))

        columns = tk.Frame(section, bg=COLORS["slate_soft"])
        columns.pack(fill="x", padx=1)
        self._configure_skill_columns(columns)
        headings = ("启用", "图标", "技能", "修改值", "当前值", "技能描述")
        for column, text in enumerate(headings):
            label = tk.Label(
                columns, text=text, anchor="center" if column in (0, 1) else "w",
                bg=COLORS["slate_soft"], fg=COLORS["muted"],
                font=("Noto Sans CJK SC", 8, "bold"),
            )
            label.grid(
                row=0, column=column,
                sticky="ew" if column in (0, 1, 5) else "w",
                padx=(8, 8), pady=7,
            )
            self.column_header_widgets[column] = label

        skills = self.configuration[self.active_group.config_name]
        for index, skill in enumerate(skills):
            row_bg = COLORS["surface"] if index % 2 == 0 else "#F8FAFC"
            row = tk.Frame(section, bg=row_bg)
            row.pack(fill="x", padx=1)
            self._configure_skill_columns(row)
            key = (self.active_group.config_name, skill)
            widgets: dict[int, tk.Widget] = {}
            enabled = tk.Checkbutton(
                row, variable=self.enabled_vars[key], command=self._update_summary,
                bg=row_bg, activebackground=row_bg, highlightthickness=0,
                anchor="center",
            )
            enabled.grid(row=0, column=0, sticky="ew", padx=8, pady=7)
            widgets[0] = enabled
            icon_image = self.skill_icon_image(skill, 34)
            icon_label = tk.Label(
                row, image=icon_image, text="—" if icon_image is None else "",
                anchor="center", bg=row_bg, fg=COLORS["muted"],
            )
            icon_label.grid(row=0, column=1, sticky="ew", padx=8, pady=4)
            widgets[1] = icon_label
            skill_label = tk.Label(
                row, text=skill, width=10, anchor="w", justify="left", wraplength=96,
                bg=row_bg, fg=COLORS["ink"], font=("Noto Sans CJK SC", 9),
            )
            skill_label.grid(row=0, column=2, sticky="nw", padx=8, pady=8)
            widgets[2] = skill_label
            value_box = tk.Frame(row, bg=row_bg)
            value_box.grid(row=0, column=3, sticky="nw", padx=8, pady=6)
            ttk.Entry(
                value_box, textvariable=self.value_vars[key], width=9
            ).pack(side="left")
            tk.Label(
                value_box, text=self.active_group.value_label, width=6, anchor="w",
                bg=row_bg, fg=COLORS["muted"], font=("Noto Sans CJK SC", 8),
            ).pack(side="left", padx=(5, 0))
            widgets[3] = value_box
            current_label = tk.Label(
                row, textvariable=self.current_value_vars[key], width=17, anchor="w",
                justify="left", wraplength=110, bg=row_bg, fg=COLORS["ink"],
                font=("Noto Sans CJK SC", 8),
            )
            current_label.grid(row=0, column=4, sticky="nw", padx=8, pady=7)
            widgets[4] = current_label
            description_label = tk.Label(
                row, textvariable=self.description_vars[skill], anchor="w",
                justify="left", wraplength=100, bg=row_bg, fg=COLORS["muted"],
                font=("Noto Sans CJK SC", 8),
            )
            description_label.grid(
                row=0, column=5, sticky="ew", padx=8, pady=7
            )
            description_label.bind(
                "<Configure>",
                lambda event, label=description_label: label.configure(
                    wraplength=max(90, event.width - 4)
                ),
            )
            widgets[5] = description_label
            self.row_column_widgets[key] = widgets
        group_name = self.active_group.config_name
        self.after_idle(lambda: self._restore_group_scroll(group_name))

    def _configure_icon_resources(self):
        IconResourcesDialog(self.app, self)

    def skill_icon_image(self, skill: str, size: int = 34):
        """Return a retained Tk image for one skill's cached PNG."""
        path = self.icon_paths.get(skill)
        if path is None or not path.is_file():
            return None
        key = (skill, int(size), str(path))
        if key not in self.icon_images:
            image = _load_tk_icon(path, int(size))
            if image is None:
                return None
            self.icon_images[key] = image
        return self.icon_images[key]

    def add_icon_listener(self, callback: Callable) -> None:
        if callback not in self.icon_listeners:
            self.icon_listeners.append(callback)

    def remove_icon_listener(self, callback: Callable) -> None:
        try:
            self.icon_listeners.remove(callback)
        except ValueError:
            pass

    def _notify_icon_listeners(self, changed_skills: frozenset[str]) -> None:
        for callback in tuple(self.icon_listeners):
            try:
                callback(changed_skills)
            except tk.TclError:
                self.remove_icon_listener(callback)

    def _icons_loaded(self, result: SpellIconSyncResult | None) -> None:
        if result is None:
            return
        changed = result.changed_skills
        self.icon_paths = dict(result.paths)
        if changed:
            old_images = self.icon_images
            self.icon_images = {
                key: image
                for key, image in old_images.items()
                if key[0] not in changed
            }
            for (_group_name, skill), widgets in self.row_column_widgets.items():
                if skill not in changed:
                    continue
                label = widgets.get(1)
                if label is None:
                    continue
                image = self.skill_icon_image(skill, 34)
                label.configure(image=image or "", text="—" if image is None else "")
                label._spell_icon_image = image
            self._notify_icon_listeners(changed)

        if result.error:
            prefix = f"图标：已加载缓存 {len(result.paths)} 项" if result.paths else "图标同步未完成"
            self.icon_status_var.set(f"{prefix} · {result.error}")
        elif changed:
            self.icon_status_var.set(
                f"图标：后台同步更新 {len(changed)} 项，缓存共 {len(result.paths)} 项"
            )
        else:
            self.icon_status_var.set(
                f"图标：缓存与数据库资源一致，共 {len(result.paths)} 项"
            )

    def refresh_icon_resources(self) -> None:
        """Reload cached images immediately, then validate them in the DB worker."""
        cached_loader = getattr(self.app, "cached_skill_icons", None)
        cached = cached_loader(self.feature, self._collect()) if cached_loader else {}
        changed = frozenset(
            skill
            for skill in set(self.icon_paths) | set(cached)
            if self.icon_paths.get(skill) != cached.get(skill)
        )
        self._icons_loaded(SpellIconSyncResult(cached, changed))
        self.icon_status_var.set(
            f"图标：已加载缓存 {len(cached)} 项，正在同步数据库与资源"
        )
        self._request_details()

    def _request_details(self):
        request = getattr(self.app, "request_skill_details", None)
        if request is None:
            self._details_loaded({}, {}, "当前界面不支持数据库技能数据查询")
            return
        self.detail_request_id += 1
        request_id = self.detail_request_id
        self.description_status_var.set("正在从当前数据库读取技能当前值与描述")

        def callback(descriptions, current_values, error="", icon_result=None):
            if request_id != self.detail_request_id:
                return
            self._details_loaded(descriptions, current_values, error, icon_result)

        configuration = self._collect()
        try:
            request(self.feature, callback, configuration)
        except TypeError:
            # Compatibility with small test/fake app objects that still expose
            # the earlier two-argument callback API.
            request(self.feature, callback)

    def _details_loaded(
        self,
        descriptions: dict[str, str],
        current_values: dict[tuple[str, str], str],
        error: str = "",
        icon_result: SpellIconSyncResult | None = None,
    ):
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return

        missing_descriptions = 0
        for skill, variable in self.description_vars.items():
            description = descriptions.get(skill, "")
            if description:
                variable.set(description)
            else:
                missing_descriptions += 1
                variable.set("当前数据库中未找到技能描述")

        missing_values = 0
        for key, variable in self.current_value_vars.items():
            current_value = current_values.get(key, "")
            if current_value:
                variable.set(current_value)
            else:
                missing_values += 1
                variable.set("未找到可修改值")

        self._icons_loaded(icon_result)
        if error:
            self.description_status_var.set(f"技能数据读取失败：{error}")
            return
        missing_parts = []
        if missing_values:
            missing_parts.append(f"当前值 {missing_values} 项未找到")
        if missing_descriptions:
            missing_parts.append(f"描述 {missing_descriptions} 项未找到")
        suffix = f" · {' · '.join(missing_parts)}" if missing_parts else ""
        self.description_status_var.set(f"技能数据来自 {self.app.profile.name}{suffix}")

    def _set_group_enabled(self, enabled: bool):
        group_name = self.active_group.config_name
        for skill in self.configuration[group_name]:
            self.enabled_vars[(group_name, skill)].set(enabled)
        self._update_summary()

    def _update_summary(self):
        enabled = sum(1 for variable in self.enabled_vars.values() if variable.get())
        custom_count = sum(
            1
            for group in self.feature.config_groups
            for skill in self.configuration[group.config_name]
            if skill in self.custom_conditions
        )
        self.summary_var.set(
            f"已启用 {enabled} / {len(self.enabled_vars)} 个技能  ·  "
            f"{len(self.feature.config_groups)} 类修改  ·  自定义 {custom_count} 项"
        )

    def _collect(self):
        configuration: dict[str, object] = {}
        for group in self.feature.config_groups:
            configuration[group.config_name] = {}
            group_values = configuration[group.config_name]
            for skill in self.configuration[group.config_name]:
                key = (group.config_name, skill)
                group_values[skill] = {
                    "enabled": self.enabled_vars[key].get(),
                    "value": self.value_vars[key].get().strip(),
                }
        configuration[CUSTOM_SKILL_CONDITIONS_KEY] = dict(self.custom_conditions)
        return configuration

    def custom_skill_rows(self):
        rows = []
        for group in self.feature.config_groups:
            for skill, item in self.configuration[group.config_name].items():
                if skill not in self.custom_conditions:
                    continue
                key = (group.config_name, skill)
                rows.append(
                    (
                        group.config_name,
                        group.title,
                        skill,
                        self.enabled_vars[key].get(),
                        self.value_vars[key].get(),
                        self.custom_conditions[skill],
                    )
                )
        return rows

    def _manage_custom_skills(self):
        CustomSkillsDialog(self)

    def _activate_group(self, group_name: str):
        group = next(
            item for item in self.feature.config_groups
            if item.config_name == group_name
        )
        if self.active_group.config_name != group_name:
            self._remember_active_group_scroll()
            self.active_group = group
        index = self.feature.config_groups.index(group)
        self.group_list.selection_clear(0, "end")
        self.group_list.selection_set(index)
        self.group_list.see(index)

    def upsert_custom_skill(
        self,
        original_group: str | None,
        original_skill: str | None,
        group_name: str,
        skill: str,
        condition: str,
        value: str,
        enabled: bool,
    ):
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
            old_key = (original_group, original_skill)
            self.configuration[original_group].pop(original_skill, None)
            self.enabled_vars.pop(old_key, None)
            self.value_vars.pop(old_key, None)
            self.current_value_vars.pop(old_key, None)

        self.configuration[group_name][skill] = {
            "enabled": bool(enabled), "value": str(value).strip()
        }
        key = (group_name, skill)
        self.enabled_vars[key] = tk.BooleanVar(self, value=bool(enabled))
        self.value_vars[key] = tk.StringVar(self, value=str(value).strip())
        self.current_value_vars[key] = tk.StringVar(self, value="正在读取…")
        if skill not in self.description_vars:
            self.description_vars[skill] = tk.StringVar(
                self, value="正在从当前数据库读取…"
            )
        else:
            self.description_vars[skill].set("正在从当前数据库读取…")
        self.custom_conditions[skill] = condition

        if original_skill and original_skill != skill:
            still_used = any(
                original_skill in self.configuration[group.config_name]
                for group in self.feature.config_groups
            )
            if not still_used:
                self.custom_conditions.pop(original_skill, None)
                self.description_vars.pop(original_skill, None)

        self._activate_group(group_name)
        self._refresh_group_list()
        self._render_group()
        self._update_summary()
        self._request_details()

    def remove_custom_skill(self, group_name: str, skill: str):
        if skill not in self.custom_conditions:
            raise ValueError("只能删除 GUI 中新增的技能。")
        self.configuration[group_name].pop(skill, None)
        key = (group_name, skill)
        self.enabled_vars.pop(key, None)
        self.value_vars.pop(key, None)
        self.current_value_vars.pop(key, None)
        still_used = any(
            skill in self.configuration[group.config_name]
            for group in self.feature.config_groups
        )
        if not still_used:
            self.custom_conditions.pop(skill, None)
            self.description_vars.pop(skill, None)
        self._refresh_group_list()
        self._render_group()
        self._update_summary()
        self._request_details()

    def _reset_defaults(self):
        if not messagebox.askyesno(
            "恢复默认配置",
            "将所有技能恢复为当前代码中的默认启用状态和数值，并删除 GUI 中新增的自定义技能？",
            parent=self,
        ):
            return
        self.configuration = self.feature.default_configuration()
        self.custom_conditions = {}
        self.enabled_vars.clear()
        self.value_vars.clear()
        self.current_value_vars.clear()
        self.description_vars.clear()
        self._initialize_variables()
        self._refresh_group_list()
        self._render_group()
        self._update_summary()
        self._request_details()

    def _save(self):
        configuration = self._collect()
        try:
            self.feature.configured_values(configuration)
        except ValueError as exc:
            messagebox.showerror("配置无效", str(exc), parent=self)
            return
        try:
            self.app.save_feature_configuration(self.feature, configuration)
        except (OSError, TypeError, ValueError) as exc:
            messagebox.showerror("保存配置失败", str(exc), parent=self)
            return
        self._back()

    def _back(self):
        self.preserve_navigation_state = False
        self.app.show_skill_category_home(self.feature)


class DbToolApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.settings: AppSettings = load_settings()
        self.spell_icon_cache = self._create_spell_icon_cache()
        self.title("Azeroth DB Forge")
        self.geometry(self.settings.window_geometry)
        self.minsize(1040, 680)
        self.configure(bg=COLORS["paper"])
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.latest: dict[str, FeatureRun] = {}
        self.category = "全部功能"
        self.search_var = tk.StringVar()
        self.status_var = tk.StringVar(value="全部状态")
        self.profile_var = tk.StringVar()
        self.connection_var = tk.StringVar(value="尚未连接")
        self.selected: dict[str, tk.BooleanVar] = {f.id: tk.BooleanVar(value=False) for f in FEATURES}
        self.work_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.skill_detail_callbacks: dict[tuple[object, ...], list[Callable]] = {}
        self.skill_navigation_states: dict[str, dict] = {}
        self.active_skill_feature_id: str | None = None
        self.current_skill_view: SkillConfigView | None = None
        self.running = False
        self.cards_frame: ScrollFrame | None = None
        self._configure_styles()
        self._build_shell()
        self.save_and_reload_profiles(refresh=False)
        self.show_features()
        self.after(120, self._poll_queue)
        self.after(250, self.refresh_state)

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
        return self.spell_icon_cache.cached_paths(
            self.profile, feature, configuration
        )

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
        saved = self.settings.feature_configs.get(feature.id, {})
        return feature.normalize_configuration(saved)

    def feature_version(self, feature: Feature) -> str:
        return feature.effective_version(self.feature_configuration(feature))

    def save_feature_configuration(self, feature: Feature, configuration) -> None:
        """Persist a skill configuration without clearing the current run state."""
        normalized = feature.normalize_configuration(configuration)
        feature.configured_values(normalized)
        feature_configs = copy.deepcopy(self.settings.feature_configs)
        feature_configs[feature.id] = normalized
        updated = replace(self.settings, feature_configs=feature_configs)
        save_settings(updated)
        self.settings = updated

    def _configure_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TButton", font=("Noto Sans CJK SC", 9), padding=(12, 7))
        style.configure("Accent.TButton", background=COLORS["gold"], foreground="white", bordercolor=COLORS["gold"], font=("Noto Sans CJK SC", 9, "bold"))
        style.map("Accent.TButton", background=[("active", "#AE7624"), ("disabled", "#C9B48E")])
        style.configure("Quiet.TButton", background=COLORS["surface"], foreground=COLORS["navy_2"], bordercolor=COLORS["line"])
        style.configure("Treeview", rowheight=32, font=("Noto Sans CJK SC", 9), background="white", fieldbackground="white")
        style.configure("Treeview.Heading", font=("Noto Sans CJK SC", 9, "bold"), foreground=COLORS["ink"])
        style.configure("TCombobox", padding=5)

    def _build_shell(self):
        top = tk.Frame(self, bg=COLORS["navy"], height=76)
        top.pack(fill="x")
        top.pack_propagate(False)
        brand = tk.Frame(top, bg=COLORS["navy"])
        brand.pack(side="left", padx=24, pady=12)
        tk.Label(brand, text="AZEROTH", fg="#9CC4D2", bg=COLORS["navy"], font=("DejaVu Sans", 8, "bold")).pack(anchor="w")
        tk.Label(brand, text="DB FORGE", fg="white", bg=COLORS["navy"], font=("DejaVu Sans", 19, "bold")).pack(anchor="w")

        target = tk.Frame(top, bg=COLORS["navy"])
        target.pack(side="right", padx=22, pady=14)
        self.profile_combo = ttk.Combobox(target, textvariable=self.profile_var, state="readonly", width=23)
        self.profile_combo.pack(side="left", padx=(0, 8))
        self.profile_combo.bind("<<ComboboxSelected>>", self._profile_changed)
        ttk.Button(target, text="连接配置", command=lambda: ProfilesDialog(self)).pack(side="left", padx=(0, 8))
        ttk.Button(target, text="刷新状态", style="Accent.TButton", command=self.refresh_state).pack(side="left")

        body = tk.Frame(self, bg=COLORS["paper"])
        body.pack(fill="both", expand=True)
        self.sidebar = tk.Frame(body, bg=COLORS["navy_2"], width=210)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self.main = tk.Frame(body, bg=COLORS["paper"])
        self.main.pack(side="left", fill="both", expand=True)
        self._build_sidebar()

    def _build_sidebar(self):
        status = tk.Frame(self.sidebar, bg="#1C3854", highlightbackground="#365872", highlightthickness=1)
        status.pack(fill="x", padx=14, pady=(18, 16))
        tk.Label(status, text="目标数据库", bg="#1C3854", fg="#91A8BC", font=("Noto Sans CJK SC", 8)).pack(anchor="w", padx=12, pady=(10, 0))
        tk.Label(status, textvariable=self.connection_var, bg="#1C3854", fg="white", font=("Noto Sans CJK SC", 9, "bold"), wraplength=165, justify="left").pack(anchor="w", padx=12, pady=(3, 10))

        self.nav_buttons: list[tk.Button] = []
        self._nav_button("全部功能", lambda: self._set_category("全部功能"))
        for category in CATEGORIES:
            self._nav_button(category, lambda c=category: self._set_category(c))
        tk.Frame(self.sidebar, height=1, bg="#46627A").pack(fill="x", padx=18, pady=12)
        self._nav_button("执行历史", self.show_history)

        bottom = tk.Frame(self.sidebar, bg=COLORS["navy_2"])
        bottom.pack(side="bottom", fill="x", padx=16, pady=16)
        tk.Label(bottom, text=f"{len(FEATURES)} 个可追踪功能", bg=COLORS["navy_2"], fg="#9DB1C2", font=("Noto Sans CJK SC", 8)).pack(anchor="w")
        tk.Label(bottom, text="状态保存在目标数据库", bg=COLORS["navy_2"], fg="#9DB1C2", font=("Noto Sans CJK SC", 8)).pack(anchor="w")

    def _nav_button(self, text: str, command: Callable):
        button = tk.Button(self.sidebar, text=text, command=command, anchor="w", relief="flat", borderwidth=0, padx=20, pady=9, bg=COLORS["navy_2"], fg="#D7E2EB", activebackground="#315572", activeforeground="white", font=("Noto Sans CJK SC", 9))
        button.pack(fill="x")
        self.nav_buttons.append(button)

    def _clear_main(self):
        view = self.current_skill_view
        if view is not None:
            try:
                if view.winfo_exists() and view.preserve_navigation_state:
                    self.skill_navigation_states[view.feature.id] = (
                        view.navigation_state()
                    )
            except tk.TclError:
                pass
            self.current_skill_view = None
        for child in self.main.winfo_children():
            child.destroy()

    def _set_category(self, category: str):
        self.category = category
        if category == "职业技能" and self.active_skill_feature_id:
            feature = FEATURE_BY_ID.get(self.active_skill_feature_id)
            if feature is not None and feature.configurable:
                if (
                    self.current_skill_view is not None
                    and self.current_skill_view.feature.id == feature.id
                ):
                    return
                self.show_skill_configuration(feature)
                return
            self.active_skill_feature_id = None
        self.show_features()

    def show_features(self):
        self._clear_main()
        header = tk.Frame(self.main, bg=COLORS["paper"])
        header.pack(fill="x", padx=28, pady=(24, 14))
        left = tk.Frame(header, bg=COLORS["paper"])
        left.pack(side="left")
        title = "功能控制台" if self.category == "全部功能" else self.category
        tk.Label(left, text=title, bg=COLORS["paper"], fg=COLORS["ink"], font=("Noto Sans CJK SC", 21, "bold")).pack(anchor="w")
        tk.Label(left, text="选择功能、确认目标数据库，然后执行。已应用记录不会再靠记忆。", bg=COLORS["paper"], fg=COLORS["muted"], font=("Noto Sans CJK SC", 9)).pack(anchor="w", pady=(3, 0))

        tools = tk.Frame(header, bg=COLORS["paper"])
        tools.pack(side="right", anchor="s")
        search = ttk.Entry(tools, textvariable=self.search_var, width=25)
        search.pack(side="left", padx=(0, 8))
        search.bind("<KeyRelease>", lambda _e: self._render_cards())
        status = ttk.Combobox(tools, textvariable=self.status_var, values=("全部状态", "未应用", "已应用", "有更新", "失败"), state="readonly", width=10)
        status.pack(side="left", padx=(0, 8))
        status.bind("<<ComboboxSelected>>", lambda _e: self._render_cards())
        ttk.Button(tools, text="应用选中", style="Accent.TButton", command=self.apply_selected).pack(side="left")

        self.summary = tk.Frame(self.main, bg=COLORS["paper"])
        self.summary.pack(fill="x", padx=28, pady=(0, 14))
        self.cards_frame = ScrollFrame(self.main, bg=COLORS["paper"])
        self.cards_frame.pack(fill="both", expand=True, padx=(28, 20), pady=(0, 22))
        self._render_summary()
        self._render_cards()

    def _run_status(self, feature: Feature) -> str:
        run = self.latest.get(feature.id)
        if not run:
            return "none"
        if run.status in ("applied", "marked") and run.feature_version != self.feature_version(feature):
            return "updated"
        return run.status if run.status in STATUS_STYLE else "none"

    def _render_summary(self):
        for child in self.summary.winfo_children():
            child.destroy()
        counts = {key: 0 for key in STATUS_STYLE}
        for feature in FEATURES:
            counts[self._run_status(feature)] += 1
        items = [
            ("已应用", counts["applied"] + counts["marked"], COLORS["teal"]),
            ("未应用", counts["none"], COLORS["muted"]),
            ("代码/配置有更新", counts["updated"], COLORS["gold"]),
            ("执行失败", counts["failed"], COLORS["red"]),
        ]
        for label, value, color in items:
            block = tk.Frame(self.summary, bg=COLORS["surface"], highlightbackground=COLORS["line"], highlightthickness=1)
            block.pack(side="left", padx=(0, 10), ipadx=13, ipady=7)
            tk.Label(block, text=str(value), bg=COLORS["surface"], fg=color, font=("DejaVu Sans", 14, "bold")).pack(side="left", padx=(3, 8))
            tk.Label(block, text=label, bg=COLORS["surface"], fg=COLORS["muted"], font=("Noto Sans CJK SC", 8)).pack(side="left", padx=(0, 3))

    def _filtered_features(self):
        query = self.search_var.get().strip().lower()
        status_filter = self.status_var.get()
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

    def _render_cards(self):
        if not self.cards_frame or not self.cards_frame.winfo_exists():
            return
        parent = self.cards_frame.inner
        for child in parent.winfo_children():
            child.destroy()
        features = list(self._filtered_features())
        if not features:
            tk.Label(parent, text="没有匹配的功能", bg=COLORS["paper"], fg=COLORS["muted"], font=("Noto Sans CJK SC", 12)).pack(pady=80)
            return
        for feature in features:
            self._create_feature_card(parent, feature)

    def _create_feature_card(self, parent, feature: Feature):
        status_key = self._run_status(feature)
        status_text, status_fg, status_bg = STATUS_STYLE[status_key]
        card = tk.Frame(parent, bg=COLORS["surface"], highlightbackground=COLORS["line"], highlightthickness=1)
        card.pack(fill="x", pady=(0, 10))
        accent = COLORS["red"] if feature.risk == "high" else COLORS["teal"]
        tk.Frame(card, bg=accent, width=5).pack(side="left", fill="y")
        check = tk.Checkbutton(card, variable=self.selected[feature.id], bg=COLORS["surface"], activebackground=COLORS["surface"], highlightthickness=0)
        check.pack(side="left", padx=(12, 4))
        text = tk.Frame(card, bg=COLORS["surface"])
        text.pack(side="left", fill="both", expand=True, padx=(4, 12), pady=13)
        title_row = tk.Frame(text, bg=COLORS["surface"])
        title_row.pack(fill="x")
        tk.Label(title_row, text=feature.title, bg=COLORS["surface"], fg=COLORS["ink"], font=("Noto Sans CJK SC", 11, "bold")).pack(side="left")
        tk.Label(title_row, text=status_text, bg=status_bg, fg=status_fg, font=("Noto Sans CJK SC", 8, "bold"), padx=8, pady=2).pack(side="left", padx=9)
        if feature.risk == "high":
            tk.Label(title_row, text="高影响", bg=COLORS["red_soft"], fg=COLORS["red"], font=("Noto Sans CJK SC", 8), padx=7, pady=2).pack(side="left")
        tk.Label(text, text=feature.description, bg=COLORS["surface"], fg=COLORS["muted"], font=("Noto Sans CJK SC", 9), anchor="w", justify="left", wraplength=670).pack(fill="x", pady=(5, 0))
        if feature.configurable:
            enabled, total = feature.configuration_summary(self.feature_configuration(feature))
            tk.Label(
                text, text=f"技能配置：已启用 {enabled} / {total} 项",
                bg=COLORS["surface"], fg=COLORS["teal"],
                font=("Noto Sans CJK SC", 8, "bold"), anchor="w",
            ).pack(fill="x", pady=(6, 0))
        meta = f"{feature.id}  ·  版本 {self.feature_version(feature)}"
        run = self.latest.get(feature.id)
        if run and run.finished_at:
            meta += f"  ·  最近 {run.finished_at}"
        tk.Label(text, text=meta, bg=COLORS["surface"], fg="#98A2B3", font=("DejaVu Sans Mono", 7), anchor="w").pack(fill="x", pady=(6, 0))

        actions = tk.Frame(card, bg=COLORS["surface"])
        actions.pack(side="right", padx=14)
        if feature.configurable:
            ttk.Button(
                actions, text="配置技能", style="Quiet.TButton",
                command=lambda f=feature: self.show_skill_configuration(f),
            ).pack(pady=(8, 5), fill="x")
            details_pady = (0, 5)
        else:
            details_pady = (8, 5)
        ttk.Button(actions, text="记录详情", style="Quiet.TButton", command=lambda f=feature: self.show_feature_details(f)).pack(pady=details_pady)
        ttk.Button(actions, text="应用功能", style="Accent.TButton", command=lambda f=feature: self.apply_features([f])).pack(pady=(0, 5), fill="x")
        ttk.Button(actions, text="仅标记已应用", style="Quiet.TButton", command=lambda f=feature: self.mark_feature(f)).pack(pady=(0, 8), fill="x")

    def show_skill_configuration(self, feature: Feature):
        if not feature.configurable:
            return
        self.category = feature.category
        self.active_skill_feature_id = feature.id
        self._clear_main()
        self.current_skill_view = SkillConfigView(
            self,
            feature,
            self.skill_navigation_states.get(feature.id),
        )

    def show_skill_category_home(self, feature: Feature | None = None):
        """Leave the class editor explicitly instead of restoring it on navigation."""
        feature_id = (
            feature.id if feature is not None else self.active_skill_feature_id
        )
        if feature_id:
            self.skill_navigation_states.pop(feature_id, None)
        self.active_skill_feature_id = None
        self.category = "职业技能"
        self.show_features()

    def apply_selected(self):
        features = [f for f in FEATURES if self.selected[f.id].get()]
        if not features:
            messagebox.showinfo("未选择功能", "请先勾选至少一个功能。", parent=self)
            return
        self.apply_features(features)

    def apply_features(self, features: list[Feature]):
        if self.running:
            messagebox.showinfo("正在执行", "请等待当前功能执行完成。", parent=self)
            return
        target = self.profile.target_label
        configurations = {feature.id: self.feature_configuration(feature) for feature in features}
        try:
            for feature in features:
                if feature.configurable:
                    enabled, _total = feature.configuration_summary(configurations[feature.id])
                    if enabled == 0:
                        raise ValueError(f"{feature.title}：没有勾选任何技能，请先打开“配置技能”。")
                    feature.configured_values(configurations[feature.id])
        except ValueError as exc:
            messagebox.showerror("技能配置无效", str(exc), parent=self)
            return

        repeated = [f.title for f in features if self._run_status(f) in ("applied", "marked")]
        high = [f.title for f in features if f.risk == "high"]
        execution_lines = []
        for feature in features:
            line = f"• {feature.title}"
            if feature.configurable:
                enabled, total = feature.configuration_summary(configurations[feature.id])
                line += f"（{enabled}/{total} 个技能）"
            execution_lines.append(line)
        detail = f"目标：{target}\n\n将执行：\n" + "\n".join(execution_lines)
        if repeated:
            detail += "\n\n以下功能已经应用过，重复执行可能继续叠加数值：\n" + "\n".join(f"• {x}" for x in repeated)
        if high:
            detail += "\n\n高影响功能：\n" + "\n".join(f"• {x}" for x in high) + "\n建议先备份数据库。"
        if not messagebox.askyesno("确认应用功能", detail, icon="warning" if high or repeated else "question", parent=self):
            return
        self.running = True
        self.connection_var.set(f"执行中 · {self.profile.name}")
        thread = threading.Thread(
            target=self._run_many_worker, args=(self.profile, features, configurations), daemon=True
        )
        thread.start()

    def _run_many_worker(self, profile: DatabaseProfile, features: list[Feature], configurations):
        results = []
        for feature in features:
            try:
                result = run_feature(profile, feature, configurations.get(feature.id))
            except Exception:
                import traceback
                error = traceback.format_exc()
                result = RunResult(False, feature, 0, error, error)
            results.append(result)
            self.work_queue.put(("progress", result))
            if not result.ok:
                break
        self.work_queue.put(("finished", results))

    def mark_feature(self, feature: Feature):
        if self.running:
            return
        configuration = self.feature_configuration(feature)
        note = "由用户手动标记为已应用"
        config_line = ""
        try:
            if feature.configurable:
                enabled, total = feature.configuration_summary(configuration)
                if enabled == 0:
                    raise ValueError(f"{feature.title}：没有勾选任何技能，请先打开“配置技能”。")
                configured = feature.configured_values(configuration)
                config_line = f"\n当前技能配置：{enabled}/{total} 项"
                details = []
                for group in feature.config_groups:
                    values = configured[group.config_name]
                    if not values:
                        continue
                    details.append(f"[{group.title}] {len(values)} 项")
                    details.extend(f"  - {skill}: {value}" for skill, value in values.items())
                if details:
                    note += "\n" + "\n".join(details)
        except ValueError as exc:
            messagebox.showerror("技能配置无效", str(exc), parent=self)
            return
        text = f"仅写入“已应用”记录，不会修改游戏数据。\n\n目标：{self.profile.target_label}\n功能：{feature.title}{config_line}\n\n用于数据库已在旧脚本中修改过、但没有历史记录的情况。"
        if not messagebox.askyesno("标记为已应用", text, parent=self):
            return
        try:
            FeatureStateStore(self.profile).mark_applied(
                feature.id, feature.title, self.feature_version(feature), note=note
            )
            self.refresh_state()
        except Exception as exc:
            messagebox.showerror("标记失败", str(exc), parent=self)

    def request_skill_details(
        self, feature: Feature, callback: Callable, configuration=None
    ) -> None:
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
            args=(
                replace(self.profile), feature, copy.deepcopy(normalized), key,
                icon_cache,
            ),
            daemon=True,
        ).start()

    @staticmethod
    def _deliver_skill_details(
        callback: Callable, descriptions, current_values, error: str,
        icon_result: SpellIconSyncResult,
    ) -> None:
        try:
            try:
                parameters = tuple(inspect.signature(callback).parameters.values())
                accepts_icons = any(
                    parameter.kind == inspect.Parameter.VAR_POSITIONAL
                    for parameter in parameters
                ) or sum(
                    parameter.kind
                    in (
                        inspect.Parameter.POSITIONAL_ONLY,
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    )
                    for parameter in parameters
                ) >= 4
            except (TypeError, ValueError):
                accepts_icons = True
            if accepts_icons:
                callback(descriptions, current_values, error, icon_result)
            else:
                # Compatibility with external/fake callers using the old callback.
                callback(descriptions, current_values, error)
        except tk.TclError:
            # The user may have left the skill page while the DB query was running.
            pass

    def _skill_detail_worker(
        self, profile: DatabaseProfile, feature: Feature, configuration, key,
        icon_cache: SpellIconCache,
    ):
        try:
            details = load_skill_details(profile, feature, configuration)
            icon_result = icon_cache.sync(
                profile, feature, configuration, details.icons
            )
            self.work_queue.put(
                (
                    "skill_details",
                    (
                        key, details.descriptions, details.current_values, "",
                        icon_result,
                    ),
                )
            )
        except Exception as exc:
            try:
                cached = icon_cache.cached_paths(profile, feature, configuration)
            except Exception:
                cached = {}
            self.work_queue.put(
                (
                    "skill_details",
                    (key, {}, {}, str(exc), SpellIconSyncResult(cached, error=str(exc))),
                )
            )

    def refresh_state(self):
        if self.running:
            return
        self.connection_var.set(f"连接中 · {self.profile.name}")
        threading.Thread(target=self._refresh_worker, args=(self.profile,), daemon=True).start()

    def _refresh_worker(self, profile: DatabaseProfile):
        try:
            store = FeatureStateStore(profile)
            version = store.test_connection()
            latest = store.latest_runs()
            self.work_queue.put(("state", (profile.target_label, version, latest)))
        except Exception as exc:
            self.work_queue.put(("state_error", (profile.target_label, str(exc))))

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.work_queue.get_nowait()
                if kind == "state":
                    target_label, version, latest = payload
                    if target_label == self.profile.target_label:
                        self.latest = latest
                        self.connection_var.set(f"已连接 · {self.profile.name}\nMySQL {version}")
                        if self.cards_frame and self.cards_frame.winfo_exists():
                            self._render_summary()
                            self._render_cards()
                elif kind == "state_error":
                    target_label, error = payload
                    if target_label == self.profile.target_label:
                        self.connection_var.set(f"连接失败 · {self.profile.name}")
                        messagebox.showerror("数据库连接失败", f"{self.profile.target_label}\n\n{error}\n\n可在“连接配置”中修改地址和账号。", parent=self)
                elif kind == "skill_details":
                    key, descriptions, current_values, error, icon_result = payload
                    callbacks = self.skill_detail_callbacks.pop(key, [])
                    for callback in callbacks:
                        self._deliver_skill_details(
                            callback, descriptions, current_values, error, icon_result
                        )
                elif kind == "progress":
                    result: RunResult = payload
                    self.connection_var.set(f"{'完成' if result.ok else '失败'} · {result.feature.title}")
                elif kind == "finished":
                    results: list[RunResult] = payload
                    self.running = False
                    for result in results:
                        self.selected[result.feature.id].set(False)
                    failed = next((r for r in results if not r.ok), None)
                    if failed:
                        messagebox.showerror("执行中止", f"{failed.feature.title} 执行失败。\n\n{failed.error[-2500:]}", parent=self)
                        self.show_result_log(failed)
                    else:
                        total = sum(r.duration_ms for r in results)
                        messagebox.showinfo("应用完成", f"已完成 {len(results)} 个功能，用时 {total / 1000:.2f} 秒。", parent=self)
                    self.refresh_state()
        except queue.Empty:
            pass
        self.after(120, self._poll_queue)

    def show_feature_details(self, feature: Feature):
        run = self.latest.get(feature.id)
        lines = [
            feature.title, "", feature.description, "", f"功能 ID：{feature.id}",
            f"当前配置版本：{self.feature_version(feature)}",
            f"调用：{feature.module}.{feature.function}",
        ]
        if feature.configurable:
            enabled, total = feature.configuration_summary(self.feature_configuration(feature))
            lines += ["", f"当前技能配置：已启用 {enabled} / {total} 项"]
        if feature.notes:
            lines += ["", "注意：" + feature.notes]
        if run:
            lines += ["", f"最近状态：{STATUS_STYLE[self._run_status(feature)][0]}", f"开始时间：{run.started_at}", f"完成时间：{run.finished_at or '-'}", f"耗时：{run.duration_ms or 0} ms"]
            if run.error_message:
                lines += ["", "错误：", run.error_message]
            if run.log_excerpt:
                lines += ["", "执行日志：", run.log_excerpt]
        else:
            lines += ["", "此数据库中还没有该功能的执行记录。"]
        self._text_dialog("功能详情", "\n".join(lines))

    def show_result_log(self, result: RunResult):
        self._text_dialog(f"执行日志 · {result.feature.title}", result.output or "（无输出）")

    def _text_dialog(self, title: str, content: str):
        win = tk.Toplevel(self)
        win.title(title)
        win.geometry("900x620")
        win.configure(bg=COLORS["paper"])
        text = tk.Text(win, wrap="word", bg="#101923", fg="#D8E5ED", insertbackground="white", relief="flat", padx=18, pady=16, font=("DejaVu Sans Mono", 9))
        text.insert("1.0", content)
        text.configure(state="disabled")
        scroll = ttk.Scrollbar(win, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(fill="both", expand=True, padx=16, pady=16)

    def show_history(self):
        self._clear_main()
        header = tk.Frame(self.main, bg=COLORS["paper"])
        header.pack(fill="x", padx=28, pady=(24, 16))
        tk.Label(header, text="执行历史", bg=COLORS["paper"], fg=COLORS["ink"], font=("Noto Sans CJK SC", 21, "bold")).pack(side="left")
        ttk.Button(header, text="刷新", style="Accent.TButton", command=self.show_history).pack(side="right")
        tree_frame = tk.Frame(self.main, bg=COLORS["surface"], highlightbackground=COLORS["line"], highlightthickness=1)
        tree_frame.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        columns = ("time", "feature", "status", "version", "duration")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        labels = {"time": "执行时间", "feature": "功能", "status": "状态", "version": "代码版本", "duration": "耗时"}
        widths = {"time": 170, "feature": 360, "status": 100, "version": 120, "duration": 100}
        for col in columns:
            tree.heading(col, text=labels[col])
            tree.column(col, width=widths[col], anchor="w")
        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        try:
            runs = FeatureStateStore(self.profile).history()
            by_iid = {}
            for run in runs:
                iid = str(run.id)
                by_iid[iid] = run
                status = STATUS_STYLE.get(run.status, (run.status, "", ""))[0]
                tree.insert("", "end", iid=iid, values=(run.started_at, run.feature_title, status, run.feature_version, f"{run.duration_ms or 0} ms"))
            def open_log(_event=None):
                selection = tree.selection()
                if selection:
                    run = by_iid[selection[0]]
                    content = run.log_excerpt or run.error_message or "（无日志）"
                    self._text_dialog(f"历史日志 · {run.feature_title}", content)
            tree.bind("<Double-1>", open_log)
        except Exception as exc:
            messagebox.showerror("无法读取历史", str(exc), parent=self)

    def apply_settings(self, settings: AppSettings, refresh=True):
        """Persist a complete settings snapshot, then publish it to the UI."""
        if not settings.profiles:
            raise ValueError("至少需要一个数据库连接。")
        settings.selected_profile = min(max(settings.selected_profile, 0), len(settings.profiles) - 1)
        save_settings(settings)
        self.settings = settings
        self._reload_profile_widgets(refresh=refresh)

    def save_dialog_geometry(self, key: str, geometry: str) -> None:
        """Persist one secondary window layout without rebuilding the main UI."""
        geometries = dict(self.settings.dialog_geometries)
        if geometries.get(key) == geometry:
            return
        geometries[key] = geometry
        updated = replace(self.settings, dialog_geometries=geometries)
        save_settings(updated)
        self.settings = updated

    def save_and_reload_profiles(self, refresh=True):
        self.apply_settings(self.settings, refresh=refresh)

    def _reload_profile_widgets(self, refresh=True):
        names = [p.name for p in self.settings.profiles]
        self.profile_combo.configure(values=names)
        self.profile_combo.current(self.settings.selected_profile)
        self.profile_var.set(names[self.settings.selected_profile])
        self.latest = {}
        self.connection_var.set(f"尚未连接 · {self.profile.name}")
        if refresh:
            self.show_features()
            self.refresh_state()

    def _profile_changed(self, _event=None):
        self.settings.selected_profile = self.profile_combo.current()
        save_settings(self.settings)
        self.latest = {}
        self.show_features()
        self.refresh_state()

    def _on_close(self):
        self.settings.window_geometry = self.geometry()
        save_settings(self.settings)
        self.destroy()


def launch() -> None:
    app = DbToolApp()
    app.mainloop()
