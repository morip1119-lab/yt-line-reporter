"""
Streamlit UI
- ダッシュボード: チャンネルタブ切替・手動実行・全チャンネル一括実行
- 設定・確認ページ
- バックグラウンドスケジューラー（毎日自動実行）
"""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import schedule
import streamlit as st

import runner
from config import REPORT_TIME, REPORTS_DIR, CHANNELS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

JST = ZoneInfo("Asia/Tokyo")

st.set_page_config(
    page_title="YouTube 日次レポーター",
    page_icon="📊",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ─── スケジューラー（シングルトン） ──────────────────────────────────────────
_scheduler_lock    = threading.Lock()
_scheduler_started = False


def _scheduler_job():
    log_path = os.path.join(REPORTS_DIR, "scheduler.log")
    for ch in CHANNELS:
        result = runner.run_report(ch, send_to_line=True)
        ts = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(
                f"[{ts}] @{ch['handle']} "
                f"success={result['success']} "
                f"line_sent={result['line_sent']} "
                f"groups={result.get('groups_sent', 0)} "
                f"warning={result.get('warning')} "
                f"error={result.get('error')}\n"
            )


def _start_scheduler():
    global _scheduler_started
    with _scheduler_lock:
        if _scheduler_started:
            return
        _scheduler_started = True

    schedule.every().day.at(REPORT_TIME).do(_scheduler_job)

    def loop():
        while True:
            schedule.run_pending()
            time.sleep(30)

    threading.Thread(target=loop, daemon=True).start()


_start_scheduler()


# ─── チャンネルタブ描画関数 ───────────────────────────────────────────────────
def _render_channel_tab(ch: dict):
    handle    = ch["handle"]
    group_ids = ch["line_group_ids"]
    result_key = f"last_result_{handle}"

    # そのチャンネル用レポートを探す（ハンドル付きファイル名優先、次に旧形式）
    any_report = sorted(
        [
            f for f in os.listdir(REPORTS_DIR)
            if f.startswith(f"report_{handle}_") and f.endswith(".png")
        ],
        reverse=True,
    )
    if not any_report:
        any_report = sorted(
            [f for f in os.listdir(REPORTS_DIR) if f.startswith("report_") and f.endswith(".png")],
            reverse=True,
        )

    col1, col2 = st.columns([2, 1])

    with col2:
        st.subheader("操作")

        groups_label = (
            f"{len(group_ids)} グループに送信"
            if group_ids
            else "送信先グループ未設定"
        )
        send_toggle = st.checkbox(
            f"LINE 送信する（{groups_label}）",
            value=bool(group_ids),
            key=f"send_toggle_{handle}",
        )

        if st.button("▶ 今すぐ実行", type="primary", use_container_width=True, key=f"run_{handle}"):
            with st.spinner("データ取得・画像生成中..."):
                result = runner.run_report(ch, send_to_line=send_toggle)
            st.session_state[result_key] = result

        last = st.session_state.get(result_key)
        if last is not None:
            if last["success"]:
                st.success("✅ レポート生成完了！")
                if last["line_sent"]:
                    n = last.get("groups_sent", 1)
                    st.success(f"📱 {n} グループに送信しました")
                elif last.get("warning"):
                    st.warning(f"⚠️ {last['warning']}")
                if last.get("error"):
                    st.error(f"❌ LINE 送信エラー: {last['error']}")

                st.metric(
                    "登録者数",
                    f"{last['subscribers']:,} 人",
                    delta=(
                        f"{last['subscriber_diff']:+,} 人"
                        if last["subscriber_diff"] is not None else None
                    ),
                )
                if last["daily_views"] is not None:
                    st.metric("昨日の再生数", f"{last['daily_views']:,} 回")
                st.metric("昨日のコメント数", f"{len(last['comments'])} 件")
            else:
                st.error(f"❌ エラー: {last['error']}")

        st.divider()
        st.subheader("過去レポート")
        if not any_report:
            st.caption("まだレポートがありません。")
        for fname in any_report[:5]:
            label = (
                fname
                .replace(f"report_{handle}_", "")
                .replace("report_", "")
                .replace(".png", "")
            )
            with st.expander(label):
                st.image(os.path.join(REPORTS_DIR, fname), use_container_width=True)

    with col1:
        last = st.session_state.get(result_key)
        preview_path = (
            last["image_path"]
            if (last and last.get("image_path") and os.path.exists(last["image_path"]))
            else None
        )
        if preview_path is None and any_report:
            preview_path = os.path.join(REPORTS_DIR, any_report[0])

        if preview_path:
            date_label = (
                os.path.basename(preview_path)
                .replace(f"report_{handle}_", "")
                .replace("report_", "")
                .replace(".png", "")
            )
            st.subheader(f"レポート（{date_label}）")
            st.image(preview_path, use_container_width=True)
        else:
            st.info("まだレポートがありません。右の「今すぐ実行」を押してください。")


# ─── サイドバー ──────────────────────────────────────────────────────────────
st.sidebar.title("📊 yt-line-reporter")
channel_labels = [f"@{ch['handle']}" for ch in CHANNELS]
st.sidebar.caption(f"チャンネル: {' / '.join(channel_labels)}")
page = st.sidebar.radio("メニュー", ["ダッシュボード", "設定・確認"], index=0)
st.sidebar.divider()
st.sidebar.info(f"🕛 自動送信: 毎日 {REPORT_TIME} (JST)")

# ─── Session State 初期化 ─────────────────────────────────────────────────────
for _ch in CHANNELS:
    _key = f"last_result_{_ch['handle']}"
    if _key not in st.session_state:
        st.session_state[_key] = None

# ─── ダッシュボードページ ─────────────────────────────────────────────────────
if page == "ダッシュボード":
    st.title("YouTube 日次レポーター")
    st.caption("LINE グループへ自動で日次レポート画像を送信するツールです。")

    # 全チャンネル一括実行（2チャンネル以上の場合のみ）
    if len(CHANNELS) > 1:
        send_all_toggle = st.checkbox(
            "LINE グループへ送信する（全チャンネル）", value=True, key="send_all"
        )
        if st.button("▶▶ 全チャンネルを一括実行", type="primary", use_container_width=True):
            for ch in CHANNELS:
                with st.spinner(f"@{ch['handle']} を処理中..."):
                    result = runner.run_report(ch, send_to_line=send_all_toggle)
                st.session_state[f"last_result_{ch['handle']}"] = result
        st.divider()

    # チャンネルごとのタブ
    tab_labels = [f"@{ch['handle']}" for ch in CHANNELS]
    tabs = st.tabs(tab_labels)
    for tab, ch in zip(tabs, CHANNELS):
        with tab:
            _render_channel_tab(ch)

# ─── 設定・確認ページ ─────────────────────────────────────────────────────────
elif page == "設定・確認":
    st.title("設定・確認")

    st.subheader("チャンネル設定")
    for i, ch in enumerate(CHANNELS, 1):
        group_display = (
            ", ".join(ch["line_group_ids"]) if ch["line_group_ids"] else "（未設定）"
        )
        st.info(f"**チャンネル {i}**: @{ch['handle']}  →  LINE グループ: {group_display}")

    st.divider()
    st.subheader("API キー設定値")
    st.caption(".env ファイルで設定します。`.env.example` をコピーして `.env` を作成してください。")

    from config import YOUTUBE_API_KEY, LINE_CHANNEL_ACCESS_TOKEN

    def masked(val: str) -> str:
        if not val:
            return "⚠️ 未設定"
        return val[:6] + "..." + val[-4:] if len(val) > 10 else "****"

    st.table({
        "項目": ["YOUTUBE_API_KEY", "LINE_CHANNEL_ACCESS_TOKEN", "REPORT_TIME"],
        "値":   [masked(YOUTUBE_API_KEY), masked(LINE_CHANNEL_ACCESS_TOKEN), f"{REPORT_TIME} (JST)"],
        "状態": [
            "✅" if YOUTUBE_API_KEY else "❌",
            "✅" if LINE_CHANNEL_ACCESS_TOKEN else "❌",
            "✅",
        ],
    })

    st.divider()
    st.subheader("LINE 接続テスト")
    if st.button("LINE Bot の接続確認"):
        from line_api import verify_credentials
        ok, msg = verify_credentials()
        if ok:
            st.success(f"✅ 接続成功: {msg}")
        else:
            st.error(f"❌ {msg}")

    st.divider()
    st.subheader("YouTube 接続テスト")
    ch_options = {f"@{ch['handle']}": ch for ch in CHANNELS}
    selected_label = st.selectbox("チャンネルを選択", list(ch_options.keys()))
    if st.button("チャンネル情報を取得"):
        if not YOUTUBE_API_KEY:
            st.error("YOUTUBE_API_KEY が未設定です")
        else:
            try:
                import youtube_api as yt
                selected_handle = ch_options[selected_label]["handle"]
                stats = yt.get_channel_stats(selected_handle)
                st.success("✅ チャンネル取得成功")
                st.write({
                    "チャンネル名": stats["channel_name"],
                    "登録者数":     f"{stats['subscribers']:,} 人",
                    "総再生数":     f"{stats['total_views']:,} 回",
                })
            except Exception as e:
                st.error(f"❌ {e}")

    st.divider()
    st.subheader("スケジューラーログ（直近 20 件）")
    log_path = os.path.join(REPORTS_DIR, "scheduler.log")
    if os.path.exists(log_path):
        with open(log_path, encoding="utf-8") as f:
            lines = f.readlines()
        st.code("".join(lines[-20:]), language="text")
    else:
        st.caption("ログなし（自動実行がまだ行われていません）")
