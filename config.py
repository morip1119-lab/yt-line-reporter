import os
from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY        = os.getenv("YOUTUBE_API_KEY", "")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
REPORT_TIME            = os.getenv("REPORT_TIME", "12:00")

DB_PATH     = os.path.join(os.path.dirname(__file__), "data", "stats.db")
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "data", "reports")

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)


def _load_channels() -> list[dict]:
    """
    .env から CHANNEL_N_YT_HANDLE / CHANNEL_N_LINE_GROUP_IDS を読み込む。

    例:
        CHANNEL_1_YT_HANDLE=marketing-zamurai
        CHANNEL_1_LINE_GROUP_IDS=Cabc123,Cdef456   ← カンマ区切りで複数グループ可
        CHANNEL_2_YT_HANDLE=kusunoki3939y
        CHANNEL_2_LINE_GROUP_IDS=Cghi789

    後方互換: CHANNEL_N_* が未設定の場合は旧形式 (YOUTUBE_CHANNEL_HANDLE / LINE_GROUP_ID) を使用。
    """
    channels: list[dict] = []
    i = 1
    while True:
        handle = os.getenv(f"CHANNEL_{i}_YT_HANDLE")
        if not handle:
            break
        raw_ids  = os.getenv(f"CHANNEL_{i}_LINE_GROUP_IDS", "")
        group_ids = [g.strip() for g in raw_ids.split(",") if g.strip()]
        channels.append({"handle": handle, "line_group_ids": group_ids})
        i += 1

    # 旧形式フォールバック
    if not channels:
        handle   = os.getenv("YOUTUBE_CHANNEL_HANDLE", "marketing-zamurai")
        group_id = os.getenv("LINE_GROUP_ID", "")
        channels.append({
            "handle": handle,
            "line_group_ids": [group_id] if group_id else [],
        })

    return channels


CHANNELS = _load_channels()

# 後方互換エイリアス（旧コードが参照している場合のため残す）
YOUTUBE_CHANNEL_HANDLE = CHANNELS[0]["handle"] if CHANNELS else ""
LINE_GROUP_ID = (
    CHANNELS[0]["line_group_ids"][0]
    if CHANNELS and CHANNELS[0]["line_group_ids"]
    else ""
)
