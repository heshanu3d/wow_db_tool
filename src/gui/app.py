from __future__ import annotations

import copy
import queue
import threading
import tkinter as tk
from dataclasses import replace
from tkinter import messagebox, ttk
from typing import Callable

from .config import AppSettings, DatabaseProfile, load_settings, save_settings
from .features import CATEGORIES, FEATURES, Feature
from .runner import RunResult, run_feature
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
        self.canvas.bind_all("<MouseWheel>", self._mousewheel)

    def _mousewheel(self, event):
        if self.winfo_exists() and self.winfo_containing(event.x_root, event.y_root):
            self.canvas.yview_scroll(int(-event.delta / 120), "units")


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
                feature_configs=copy.deepcopy(self.app.settings.feature_configs),
            )
            # Persist first. The dialog remains open and reports an actionable
            # error if the file cannot be written; it is no longer closed after
            # a failed save.
            self.app.apply_settings(updated)
        except (OSError, ValueError, TypeError) as exc:
            messagebox.showerror("保存连接失败", str(exc), parent=self)
            return
        self.destroy()


class SkillConfigView(tk.Frame):
    """Detailed per-skill editor for one class bundle."""

    def __init__(self, app: "DbToolApp", feature: Feature):
        super().__init__(app.main, bg=COLORS["paper"])
        self.app = app
        self.feature = feature
        saved = app.settings.feature_configs.get(feature.id, {})
        self.configuration = feature.normalize_configuration(saved)
        self.enabled_vars: dict[tuple[str, str], tk.BooleanVar] = {}
        self.value_vars: dict[tuple[str, str], tk.StringVar] = {}
        for group_name, skills in self.configuration.items():
            for skill, item in skills.items():
                key = (group_name, skill)
                self.enabled_vars[key] = tk.BooleanVar(self, value=item["enabled"])
                self.value_vars[key] = tk.StringVar(self, value=item["value"])
        self.active_group = feature.config_groups[0]
        self.summary_var = tk.StringVar(self)
        self.pack(fill="both", expand=True)
        self._build()
        self._render_group()
        self._update_summary()

    def _build(self):
        header = tk.Frame(self, bg=COLORS["paper"])
        header.pack(fill="x", padx=28, pady=(22, 14))
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
            title_box, text="勾选需要修改的技能，并填写目标数值或倍率。默认值来自当前代码。",
            bg=COLORS["paper"], fg=COLORS["muted"], font=("Noto Sans CJK SC", 9),
        ).pack(anchor="w", pady=(4, 0))

        header_actions = tk.Frame(header, bg=COLORS["paper"])
        header_actions.pack(side="right", anchor="s")
        ttk.Button(header_actions, text="恢复代码默认值", command=self._reset_defaults).pack(side="left", padx=(0, 8))
        ttk.Button(header_actions, text="保存配置", style="Accent.TButton", command=self._save).pack(side="left")

        summary = tk.Frame(self, bg=COLORS["navy"], height=48)
        summary.pack(fill="x", padx=28, pady=(0, 14))
        summary.pack_propagate(False)
        tk.Label(
            summary, textvariable=self.summary_var, bg=COLORS["navy"], fg="white",
            font=("Noto Sans CJK SC", 10, "bold"),
        ).pack(side="left", padx=16)
        tk.Label(
            summary, text="未勾选的技能不会执行数据库修改", bg=COLORS["navy"],
            fg="#B8C8D7", font=("Noto Sans CJK SC", 9),
        ).pack(side="right", padx=16)

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
        for group in self.feature.config_groups:
            count = len(self.configuration[group.config_name])
            self.group_list.insert("end", f"  {group.title}  ·  {count}")
        self.group_list.selection_set(0)
        self.group_list.bind("<<ListboxSelect>>", self._group_selected)

        self.detail = ScrollFrame(body, bg=COLORS["paper"])
        self.detail.pack(side="left", fill="both", expand=True, padx=(16, 0))

    def _group_selected(self, _event=None):
        selected = self.group_list.curselection()
        if not selected:
            return
        self.active_group = self.feature.config_groups[selected[0]]
        self._render_group()

    def _render_group(self):
        parent = self.detail.inner
        for child in parent.winfo_children():
            child.destroy()

        section = tk.Frame(parent, bg=COLORS["surface"], highlightbackground=COLORS["line"], highlightthickness=1)
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
        ttk.Button(tools, text="全选", style="Quiet.TButton", command=lambda: self._set_group_enabled(True)).pack(side="left")
        ttk.Button(tools, text="全不选", style="Quiet.TButton", command=lambda: self._set_group_enabled(False)).pack(side="left", padx=(6, 0))

        columns = tk.Frame(section, bg=COLORS["slate_soft"])
        columns.pack(fill="x", padx=1)
        tk.Label(columns, text="启用", width=7, bg=COLORS["slate_soft"], fg=COLORS["muted"], font=("Noto Sans CJK SC", 8, "bold")).pack(side="left", pady=7)
        tk.Label(columns, text="技能", anchor="w", bg=COLORS["slate_soft"], fg=COLORS["muted"], font=("Noto Sans CJK SC", 8, "bold")).pack(side="left", fill="x", expand=True)
        tk.Label(columns, text="修改值", width=16, bg=COLORS["slate_soft"], fg=COLORS["muted"], font=("Noto Sans CJK SC", 8, "bold")).pack(side="right")

        skills = self.configuration[self.active_group.config_name]
        for index, skill in enumerate(skills):
            row_bg = COLORS["surface"] if index % 2 == 0 else "#F8FAFC"
            row = tk.Frame(section, bg=row_bg, highlightbackground=COLORS["line"], highlightthickness=0)
            row.pack(fill="x", padx=1)
            key = (self.active_group.config_name, skill)
            tk.Checkbutton(
                row, variable=self.enabled_vars[key], command=self._update_summary,
                bg=row_bg, activebackground=row_bg, highlightthickness=0, width=5,
            ).pack(side="left", padx=(7, 2), pady=7)
            tk.Label(
                row, text=skill, anchor="w", bg=row_bg, fg=COLORS["ink"],
                font=("Noto Sans CJK SC", 9),
            ).pack(side="left", fill="x", expand=True)
            # Do not disable geometry propagation here. A Frame with only a
            # configured width otherwise keeps Tk's default 1px height and clips
            # the Entry completely, making its bound default value invisible and
            # preventing mouse interaction.
            value_box = tk.Frame(row, bg=row_bg)
            value_box.pack(side="right", padx=(8, 14), pady=6)
            ttk.Entry(value_box, textvariable=self.value_vars[key], width=14).pack(side="left")
            tk.Label(
                value_box, text=self.active_group.value_label, width=7, anchor="w",
                bg=row_bg, fg=COLORS["muted"], font=("Noto Sans CJK SC", 8),
            ).pack(side="left", padx=(7, 0))

    def _set_group_enabled(self, enabled: bool):
        group_name = self.active_group.config_name
        for skill in self.configuration[group_name]:
            self.enabled_vars[(group_name, skill)].set(enabled)
        self._update_summary()

    def _update_summary(self):
        enabled = sum(1 for variable in self.enabled_vars.values() if variable.get())
        self.summary_var.set(
            f"已启用 {enabled} / {len(self.enabled_vars)} 个技能  ·  "
            f"{len(self.feature.config_groups)} 类修改"
        )

    def _collect(self):
        configuration: dict[str, dict[str, dict[str, object]]] = {}
        for group in self.feature.config_groups:
            configuration[group.config_name] = {}
            for skill in self.configuration[group.config_name]:
                key = (group.config_name, skill)
                configuration[group.config_name][skill] = {
                    "enabled": self.enabled_vars[key].get(),
                    "value": self.value_vars[key].get().strip(),
                }
        return configuration

    def _reset_defaults(self):
        if not messagebox.askyesno("恢复默认配置", "将所有技能恢复为当前代码中的默认启用状态和数值？", parent=self):
            return
        defaults = self.feature.default_configuration()
        for group_name, skills in defaults.items():
            for skill, item in skills.items():
                key = (group_name, skill)
                self.enabled_vars[key].set(item["enabled"])
                self.value_vars[key].set(item["value"])
        self._render_group()
        self._update_summary()

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
        self.app.category = "职业技能"
        self.app.show_features()


class DbToolApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.settings: AppSettings = load_settings()
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
        for child in self.main.winfo_children():
            child.destroy()

    def _set_category(self, category: str):
        self.category = category
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
        self._clear_main()
        SkillConfigView(self, feature)

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
