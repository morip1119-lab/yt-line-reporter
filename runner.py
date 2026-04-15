"""
レポート生成・送信のメインロジック。
channel_cfg = {"handle": str, "line_group_ids": [str, ...]}
"""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import data_store
import youtube_api
import report_generator
import line_api
from config import LINE_CHANNEL_ACCESS_TOKEN, YOUTUBE_API_KEY

JST = ZoneInfo("Asia/Tokyo")


def run_report(channel_cfg: dict, send_to_line: bool = True) -> dict:
    """
    指定チャンネルのレポートを生成し、設定された全 LINE グループへ送信する。

    channel_cfg:
        handle        : YouTube チャンネルハンドル (@ なし)
        line_group_ids: 送信先 LINE グループ ID のリスト（複数可）

    Returns dict:
        success      bool
        line_sent    bool  (1件以上送信成功)
        groups_sent  int   (送信成功グループ数)
        warning      str|None
        error        str|None
        image_path   str|None
        channel_name str
        subscribers  int
        subscriber_diff int|None
        daily_views  int|None
        comments     list
        top_videos   list
    """
    handle    = channel_cfg.get("handle", "")
    group_ids = channel_cfg.get("line_group_ids", [])

    result: dict = {
        "success":         False,
        "line_sent":       False,
        "groups_sent":     0,
        "warning":         None,
        "error":           None,
        "image_path":      None,
        "channel_name":    "",
        "subscribers":     0,
        "subscriber_diff": None,
        "daily_views":     None,
        "comments":        [],
        "top_videos":      [],
    }

    if not YOUTUBE_API_KEY:
        result["error"] = "YOUTUBE_API_KEY が設定されていません（.env を確認）"
        return result

    try:
        # ── YouTube チャンネル統計 ─────────────────────────────────────────
        stats        = youtube_api.get_channel_stats(handle)
        channel_id   = stats["channel_id"]
        channel_name = stats["channel_name"]
        subscribers  = stats["subscribers"]
        total_views  = stats["total_views"]

        today = datetime.now(JST).date()
        data_store.init_db(handle)

        daily_views     = data_store.save_daily_stats(handle, today, subscribers, total_views)
        subscriber_diff = data_store.get_subscriber_diff(handle, today)

        # ── 昨日のコメント ────────────────────────────────────────────────
        comments = youtube_api.get_yesterday_comments(channel_id)
        data_store.save_comments(handle, today - timedelta(days=1), comments)

        # ── 動画別再生数スナップショット（ショート除外） ──────────────────
        videos_snapshot = youtube_api.get_channel_videos_snapshot(channel_id, max_videos=50)
        data_store.save_video_views(handle, today, videos_snapshot)

        top_videos = data_store.get_top_videos_by_daily_views(handle, today, limit=10)

        # ── 画像生成 ──────────────────────────────────────────────────────
        image_path = report_generator.generate_report(
            channel_name=channel_name,
            report_date=today,
            subscribers=subscribers,
            subscriber_diff=subscriber_diff,
            daily_views=daily_views,
            comments=comments,
            top_videos=top_videos,
            channel_handle=handle,
        )

        result.update({
            "success":         True,
            "channel_name":    channel_name,
            "subscribers":     subscribers,
            "subscriber_diff": subscriber_diff,
            "daily_views":     daily_views,
            "comments":        comments,
            "top_videos":      top_videos,
            "image_path":      image_path,
        })

        # ── LINE 送信 ─────────────────────────────────────────────────────
        if send_to_line:
            if not LINE_CHANNEL_ACCESS_TOKEN:
                result["warning"] = "LINE_CHANNEL_ACCESS_TOKEN が未設定のため送信をスキップしました"
            elif not group_ids:
                result["warning"] = "送信先 LINE グループ ID が設定されていません"
            else:
                line_api.send_image_to_group(image_path, group_ids)
                result["line_sent"]   = True
                result["groups_sent"] = len(group_ids)

    except Exception as e:
        result["error"] = str(e)

    return result
