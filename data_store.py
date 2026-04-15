"""
SQLite データストア。
各テーブルには channel（YT ハンドル名）カラムを持ち、複数チャンネルのデータを分離する。

既存 DB（channel カラムなし）からの自動マイグレーション対応。
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from config import DB_PATH


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# ──────────────────────────────────────────────────────────────────────────────
# DB 初期化 & マイグレーション
# ──────────────────────────────────────────────────────────────────────────────

def init_db(channel_handle: str = ""):
    """
    テーブルを作成し、旧スキーマ（channel カラムなし）からのマイグレーションを実行する。
    channel_handle は既存データへのデフォルト値として使用する。
    """
    with _get_conn() as conn:
        # まず旧テーブルが存在する場合にマイグレーション
        _migrate_add_channel(conn, channel_handle)

        # 新スキーマでテーブル作成（存在しない場合のみ）
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                channel     TEXT NOT NULL DEFAULT '',
                date        TEXT NOT NULL,
                subscribers INTEGER,
                total_views INTEGER,
                daily_views INTEGER,
                PRIMARY KEY (channel, date)
            );
            CREATE TABLE IF NOT EXISTS daily_comments (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT NOT NULL DEFAULT '',
                date    TEXT,
                author  TEXT,
                text    TEXT,
                published TEXT,
                video_id  TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_daily_comments_channel_date
                ON daily_comments(channel, date);
            CREATE TABLE IF NOT EXISTS video_daily_views (
                channel     TEXT NOT NULL DEFAULT '',
                date        TEXT NOT NULL,
                video_id    TEXT NOT NULL,
                title       TEXT,
                thumbnail   TEXT,
                total_views INTEGER,
                PRIMARY KEY (channel, date, video_id)
            );
        """)


def _migrate_add_channel(conn: sqlite3.Connection, default_channel: str):
    """
    旧スキーマ（channel カラムなし）を新スキーマへ移行する。
    既に移行済みの場合は何もしない。
    """
    cols = {row[1] for row in conn.execute("PRAGMA table_info(daily_stats)")}
    if "channel" in cols:
        return  # 既にマイグレーション済み

    ch = default_channel or ""

    # daily_stats
    _exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='daily_stats'"
    ).fetchone()
    if _exists:
        conn.execute("ALTER TABLE daily_stats RENAME TO _ds_old")
        conn.execute("""
            CREATE TABLE daily_stats (
                channel     TEXT NOT NULL DEFAULT '',
                date        TEXT NOT NULL,
                subscribers INTEGER,
                total_views INTEGER,
                daily_views INTEGER,
                PRIMARY KEY (channel, date)
            )
        """)
        conn.execute(
            "INSERT INTO daily_stats (channel, date, subscribers, total_views, daily_views) "
            "SELECT ?, date, subscribers, total_views, daily_views FROM _ds_old",
            (ch,),
        )
        conn.execute("DROP TABLE _ds_old")

    # daily_comments
    _exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='daily_comments'"
    ).fetchone()
    if _exists:
        conn.execute("ALTER TABLE daily_comments RENAME TO _dc_old")
        conn.execute("""
            CREATE TABLE daily_comments (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT NOT NULL DEFAULT '',
                date    TEXT,
                author  TEXT,
                text    TEXT,
                published TEXT,
                video_id  TEXT
            )
        """)
        conn.execute(
            "INSERT INTO daily_comments (channel, date, author, text, published, video_id) "
            "SELECT ?, date, author, text, published, video_id FROM _dc_old",
            (ch,),
        )
        conn.execute("DROP TABLE _dc_old")
        conn.execute("DROP INDEX IF EXISTS idx_daily_comments_date")

    # video_daily_views
    _exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='video_daily_views'"
    ).fetchone()
    if _exists:
        conn.execute("ALTER TABLE video_daily_views RENAME TO _vdv_old")
        conn.execute("""
            CREATE TABLE video_daily_views (
                channel     TEXT NOT NULL DEFAULT '',
                date        TEXT NOT NULL,
                video_id    TEXT NOT NULL,
                title       TEXT,
                thumbnail   TEXT,
                total_views INTEGER,
                PRIMARY KEY (channel, date, video_id)
            )
        """)
        conn.execute(
            "INSERT INTO video_daily_views (channel, date, video_id, title, thumbnail, total_views) "
            "SELECT ?, date, video_id, title, thumbnail, total_views FROM _vdv_old",
            (ch,),
        )
        conn.execute("DROP TABLE _vdv_old")


# ──────────────────────────────────────────────────────────────────────────────
# 日次統計
# ──────────────────────────────────────────────────────────────────────────────

def save_daily_stats(
    channel: str, stats_date: date, subscribers: int, total_views: int
) -> int | None:
    yesterday = stats_date - timedelta(days=1)
    prev = get_stats(channel, yesterday)
    daily_views = total_views - prev["total_views"] if prev else None

    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO daily_stats (channel, date, subscribers, total_views, daily_views)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(channel, date) DO UPDATE SET
                subscribers = excluded.subscribers,
                total_views = excluded.total_views,
                daily_views = excluded.daily_views
            """,
            (channel, str(stats_date), subscribers, total_views, daily_views),
        )
    return daily_views


def get_stats(channel: str, stats_date: date) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM daily_stats WHERE channel = ? AND date = ?",
            (channel, str(stats_date)),
        ).fetchone()
    return dict(row) if row else None


def get_subscriber_diff(channel: str, today: date) -> int | None:
    today_stats     = get_stats(channel, today)
    yesterday_stats = get_stats(channel, today - timedelta(days=1))
    if today_stats and yesterday_stats:
        return today_stats["subscribers"] - yesterday_stats["subscribers"]
    return None


# ──────────────────────────────────────────────────────────────────────────────
# コメント
# ──────────────────────────────────────────────────────────────────────────────

def save_comments(channel: str, comments_date: date, comments: list[dict]):
    with _get_conn() as conn:
        conn.execute(
            "DELETE FROM daily_comments WHERE channel = ? AND date = ?",
            (channel, str(comments_date)),
        )
        conn.executemany(
            """
            INSERT INTO daily_comments (channel, date, author, text, published, video_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    channel,
                    str(comments_date),
                    c.get("author", ""),
                    c.get("text", ""),
                    c.get("published", ""),
                    c.get("video_id", ""),
                )
                for c in comments
            ],
        )


def get_comments(channel: str, comments_date: date) -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM daily_comments WHERE channel = ? AND date = ? ORDER BY published DESC",
            (channel, str(comments_date)),
        ).fetchall()
    return [dict(r) for r in rows]


# ──────────────────────────────────────────────────────────────────────────────
# 動画別再生数スナップショット
# ──────────────────────────────────────────────────────────────────────────────

def save_video_views(channel: str, snapshot_date: date, videos: list[dict]):
    """
    videos: [{"video_id", "title", "thumbnail", "total_views"}]
    """
    with _get_conn() as conn:
        conn.executemany(
            """
            INSERT INTO video_daily_views (channel, date, video_id, title, thumbnail, total_views)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(channel, date, video_id) DO UPDATE SET
                title       = excluded.title,
                thumbnail   = excluded.thumbnail,
                total_views = excluded.total_views
            """,
            [
                (
                    channel,
                    str(snapshot_date),
                    v["video_id"],
                    v["title"],
                    v["thumbnail"],
                    v["total_views"],
                )
                for v in videos
            ],
        )


def get_top_videos_by_daily_views(
    channel: str, today: date, limit: int = 10
) -> list[dict]:
    """
    前日比の再生増加数が多い動画 TOP N を返す。
    前日スナップショットが存在しない動画は除外（初出日バグ防止）。
    """
    yesterday = today - timedelta(days=1)
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                t.video_id,
                t.title,
                t.thumbnail,
                t.total_views,
                (t.total_views - y.total_views) AS daily_views
            FROM video_daily_views t
            INNER JOIN video_daily_views y
                    ON t.channel = y.channel
                   AND t.video_id = y.video_id
                   AND y.date = ?
            WHERE t.channel = ?
              AND t.date = ?
              AND (t.total_views - y.total_views) > 0
            ORDER BY daily_views DESC
            LIMIT ?
            """,
            (str(yesterday), channel, str(today), limit),
        ).fetchall()
    return [dict(r) for r in rows]
