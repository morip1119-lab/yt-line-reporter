import logging
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import YOUTUBE_API_KEY

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

_ISO_DURATION_RE = re.compile(
    r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", re.IGNORECASE
)


def _duration_seconds(iso: str) -> int:
    m = _ISO_DURATION_RE.match(iso or "")
    if not m:
        return 0
    h, mi, s = (int(v or 0) for v in m.groups())
    return h * 3600 + mi * 60 + s


def _is_short(title: str, description: str, duration_sec: int) -> bool:
    if duration_sec <= 60:
        return True
    lower = (title + " " + description).lower()
    return "#shorts" in lower or "#short" in lower


def _build_service():
    return build("youtube", "v3", developerKey=YOUTUBE_API_KEY, cache_discovery=False)


def get_channel_id(channel_handle: str, service=None) -> str:
    svc = service or _build_service()
    res = svc.channels().list(
        part="id",
        forHandle=channel_handle,
    ).execute()
    items = res.get("items", [])
    if not items:
        raise ValueError(f"チャンネルが見つかりません: @{channel_handle}")
    return items[0]["id"]


def get_channel_stats(channel_handle: str) -> dict:
    """
    登録者数・総再生数・チャンネル名を返す。
    {
        "channel_id": str,
        "channel_name": str,
        "subscribers": int,
        "total_views": int,
    }
    """
    svc = _build_service()
    channel_id = get_channel_id(channel_handle, svc)

    res = svc.channels().list(
        part="statistics,snippet",
        id=channel_id,
    ).execute()

    items = res.get("items", [])
    if not items:
        raise ValueError(f"チャンネル統計が取得できませんでした: {channel_id}")

    item  = items[0]
    stats = item["statistics"]
    return {
        "channel_id":   channel_id,
        "channel_name": item["snippet"]["title"],
        "subscribers":  int(stats.get("subscriberCount", 0)),
        "total_views":  int(stats.get("viewCount", 0)),
    }


def get_yesterday_comments(channel_id: str) -> list[dict]:
    """
    昨日 (JST) に投稿されたコメントを最大 50 件返す。
    [{"author": str, "text": str, "published": str, "video_id": str}]
    """
    svc = _build_service()

    now_jst       = datetime.now(JST)
    yesterday_jst = (now_jst - timedelta(days=1)).date()
    after  = datetime(yesterday_jst.year, yesterday_jst.month, yesterday_jst.day,
                      0, 0, 0, tzinfo=JST).isoformat()
    before = datetime(yesterday_jst.year, yesterday_jst.month, yesterday_jst.day,
                      23, 59, 59, tzinfo=JST).isoformat()

    try:
        search_res = svc.search().list(
            part="id",
            channelId=channel_id,
            type="video",
            publishedAfter=after,
            publishedBefore=before,
            maxResults=10,
            order="date",
        ).execute()
        video_ids = [item["id"]["videoId"] for item in search_res.get("items", [])]
    except HttpError as e:
        logger.warning("動画検索に失敗しました (status=%s): %s", e.status_code, e.reason)
        video_ids = []

    comments: list[dict] = []

    for video_id in video_ids:
        try:
            ct_res = svc.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=10,
                order="time",
            ).execute()
            for item in ct_res.get("items", []):
                top = item["snippet"]["topLevelComment"]["snippet"]
                comments.append({
                    "author":    top["authorDisplayName"],
                    "text":      top["textDisplay"],
                    "published": top["publishedAt"],
                    "video_id":  video_id,
                })
        except HttpError as e:
            logger.warning(
                "コメント取得に失敗しました video_id=%s (status=%s): %s",
                video_id, e.status_code, e.reason,
            )

    try:
        all_ct_res = svc.commentThreads().list(
            part="snippet",
            allThreadsRelatedToChannelId=channel_id,
            maxResults=20,
            order="time",
        ).execute()
        for item in all_ct_res.get("items", []):
            top       = item["snippet"]["topLevelComment"]["snippet"]
            published = top["publishedAt"]
            if published[:10] == str(yesterday_jst):
                vid_id = item["snippet"].get("videoId", "")
                entry  = {
                    "author":    top["authorDisplayName"],
                    "text":      top["textDisplay"],
                    "published": published,
                    "video_id":  vid_id,
                }
                if entry not in comments:
                    comments.append(entry)
    except HttpError as e:
        logger.warning(
            "チャンネルコメント取得に失敗しました (status=%s): %s", e.status_code, e.reason
        )

    seen: set[tuple] = set()
    unique: list[dict] = []
    for c in comments:
        key = (c["author"], c["text"][:30])
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique[:50]


def get_channel_videos_snapshot(channel_id: str, max_videos: int = 50) -> list[dict]:
    """
    チャンネルの最近の動画（ショート除外）の現在の再生数スナップショットを返す。
    [{"video_id", "title", "thumbnail", "total_views"}]
    """
    svc = _build_service()

    video_ids: list[str] = []
    next_page = None
    while len(video_ids) < max_videos:
        params: dict = dict(
            part="id",
            channelId=channel_id,
            type="video",
            order="date",
            maxResults=min(50, max_videos - len(video_ids)),
        )
        if next_page:
            params["pageToken"] = next_page
        try:
            res = svc.search().list(**params).execute()
        except HttpError as e:
            logger.warning("動画一覧取得に失敗しました (status=%s): %s", e.status_code, e.reason)
            break
        for item in res.get("items", []):
            video_ids.append(item["id"]["videoId"])
        next_page = res.get("nextPageToken")
        if not next_page:
            break

    if not video_ids:
        return []

    results: list[dict] = []
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i : i + 50]
        try:
            vid_res = svc.videos().list(
                part="snippet,statistics,contentDetails",
                id=",".join(chunk),
            ).execute()
        except HttpError as e:
            logger.warning("動画詳細取得に失敗しました (status=%s): %s", e.status_code, e.reason)
            continue

        for item in vid_res.get("items", []):
            snippet = item["snippet"]
            stats   = item["statistics"]
            details = item["contentDetails"]

            duration_sec = _duration_seconds(details.get("duration", ""))
            title        = snippet.get("title", "")
            description  = snippet.get("description", "")

            if _is_short(title, description, duration_sec):
                continue

            thumbnails = snippet.get("thumbnails", {})
            thumbnail  = (
                thumbnails.get("medium", {}).get("url")
                or thumbnails.get("default", {}).get("url")
                or ""
            )

            results.append({
                "video_id":    item["id"],
                "title":       title,
                "thumbnail":   thumbnail,
                "total_views": int(stats.get("viewCount", 0)),
            })

    return results
