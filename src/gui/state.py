from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import mysql.connector

from .config import DatabaseProfile

TABLE_NAME = "db_tool_feature_runs"


@dataclass
class FeatureRun:
    id: int
    feature_id: str
    feature_title: str
    feature_version: str
    status: str
    started_at: Any
    finished_at: Any
    duration_ms: int | None
    error_message: str | None
    log_excerpt: str | None


class FeatureStateStore:
    def __init__(self, profile: DatabaseProfile):
        self.profile = profile

    def _connect(self):
        return mysql.connector.connect(**self.profile.connector_config())

    def test_connection(self) -> str:
        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()[0]
            cursor.close()
            return str(version)
        finally:
            connection.close()

    def ensure_schema(self) -> None:
        sql = f"""
        CREATE TABLE IF NOT EXISTS `{TABLE_NAME}` (
            `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            `feature_id` VARCHAR(128) NOT NULL,
            `feature_title` VARCHAR(255) NOT NULL,
            `feature_version` VARCHAR(64) NOT NULL,
            `status` VARCHAR(24) NOT NULL,
            `started_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `finished_at` DATETIME(6) NULL,
            `duration_ms` BIGINT NULL,
            `error_message` TEXT NULL,
            `log_excerpt` MEDIUMTEXT NULL,
            PRIMARY KEY (`id`),
            KEY `idx_feature_started` (`feature_id`, `started_at`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute(sql)
            connection.commit()
            cursor.close()
        finally:
            connection.close()

    def latest_runs(self) -> dict[str, FeatureRun]:
        self.ensure_schema()
        sql = f"""
        SELECT r.id, r.feature_id, r.feature_title, r.feature_version, r.status,
               r.started_at, r.finished_at, r.duration_ms, r.error_message, r.log_excerpt
        FROM `{TABLE_NAME}` r
        INNER JOIN (
            SELECT feature_id, MAX(id) AS max_id
            FROM `{TABLE_NAME}`
            GROUP BY feature_id
        ) latest ON latest.max_id = r.id
        """
        return {run.feature_id: run for run in self._query_runs(sql)}

    def history(self, limit: int = 300) -> list[FeatureRun]:
        self.ensure_schema()
        sql = f"""
        SELECT id, feature_id, feature_title, feature_version, status,
               started_at, finished_at, duration_ms, error_message, log_excerpt
        FROM `{TABLE_NAME}`
        ORDER BY id DESC
        LIMIT %s
        """
        return self._query_runs(sql, (limit,))

    def _query_runs(self, sql: str, params: tuple[Any, ...] = ()) -> list[FeatureRun]:
        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute(sql, params)
            runs = [FeatureRun(*row) for row in cursor.fetchall()]
            cursor.close()
            return runs
        finally:
            connection.close()

    def begin(self, feature_id: str, title: str, version: str) -> int:
        self.ensure_schema()
        sql = f"""
        INSERT INTO `{TABLE_NAME}`
            (feature_id, feature_title, feature_version, status, started_at)
        VALUES (%s, %s, %s, 'running', %s)
        """
        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute(sql, (feature_id, title, version, datetime.now()))
            run_id = int(cursor.lastrowid)
            connection.commit()
            cursor.close()
            return run_id
        finally:
            connection.close()

    def finish(self, run_id: int, status: str, duration_ms: int, log: str = "", error: str = "") -> None:
        sql = f"""
        UPDATE `{TABLE_NAME}`
        SET status=%s, finished_at=%s, duration_ms=%s, error_message=%s, log_excerpt=%s
        WHERE id=%s
        """
        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute(sql, (status, datetime.now(), duration_ms, error[-8000:] or None, log[-60000:] or None, run_id))
            connection.commit()
            cursor.close()
        finally:
            connection.close()

    def mark_applied(self, feature_id: str, title: str, version: str, note: str = "由用户手动标记为已应用") -> None:
        self.ensure_schema()
        sql = f"""
        INSERT INTO `{TABLE_NAME}`
            (feature_id, feature_title, feature_version, status, started_at, finished_at, duration_ms, log_excerpt)
        VALUES (%s, %s, %s, 'marked', %s, %s, 0, %s)
        """
        now = datetime.now()
        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute(sql, (feature_id, title, version, now, now, note))
            connection.commit()
            cursor.close()
        finally:
            connection.close()
