from __future__ import annotations

import contextlib
import io
import time
import traceback
from dataclasses import dataclass

from src.core.mysql_core import Mysql

from .config import DatabaseProfile
from .features import Feature
from .state import FeatureStateStore


@dataclass
class RunResult:
    ok: bool
    feature: Feature
    duration_ms: int
    output: str
    error: str = ""


def run_feature(profile: DatabaseProfile, feature: Feature, configuration=None) -> RunResult:
    """Run one feature and guarantee a result object even if tracking fails."""
    started = time.perf_counter()
    store = FeatureStateStore(profile)
    effective_version = feature.effective_version(configuration)
    try:
        run_id = store.begin(feature.id, feature.title, effective_version)
    except Exception:
        error = "无法在目标数据库创建执行记录，因此功能尚未运行。\n" + traceback.format_exc()
        return RunResult(False, feature, int((time.perf_counter() - started) * 1000), error, error)

    output = io.StringIO()
    error = ""
    feature_ok = False
    try:
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            instance = Mysql(config=profile.connector_config(), strict=True)
            feature.execute(instance, configuration)
        feature_ok = True
    except Exception:
        error = traceback.format_exc()
        output.write("\n" + error)

    duration_ms = int((time.perf_counter() - started) * 1000)
    text = output.getvalue()
    try:
        store.finish(run_id, "applied" if feature_ok else "failed", duration_ms, text, error)
    except Exception:
        state_error = traceback.format_exc()
        warning = (
            "\n状态记录写入失败。"
            + ("数据库功能可能已经执行成功，请勿直接重复应用；修复记录表后可使用“仅标记已应用”。\n" if feature_ok else "\n")
            + state_error
        )
        text += warning
        return RunResult(False, feature, duration_ms, text, warning)

    return RunResult(feature_ok, feature, duration_ms, text, error)
