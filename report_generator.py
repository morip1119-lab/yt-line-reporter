"""
HTML (Tailwind CSS) → Playwright スクリーンショット → PNG 画像を生成するモジュール。
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import date
from pathlib import Path

import requests

# Python 3.14 + Windows の asyncio 互換性パッチ（Playwright が subprocess を使うため必須）
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from report_html import generate_html
from config import REPORTS_DIR

logger = logging.getLogger(__name__)

_TAILWIND_CDN_URL = "https://cdn.tailwindcss.com"
_TAILWIND_CACHE   = os.path.join(os.path.dirname(__file__), "assets", "tailwind.min.js")


def _ensure_tailwind_cached() -> str:
    """後方互換のため残す（現在の HTML テンプレートは Tailwind 不使用）。"""
    return ""


def generate_report(
    channel_name: str,
    report_date: date,
    subscribers: int,
    subscriber_diff: int | None,
    daily_views: int | None,
    comments: list[dict],
    top_videos: list[dict] | None = None,
    save_path: str | None = None,
    channel_handle: str = "",
) -> str:
    """
    HTML レポートを生成し Playwright でスクリーンショットを撮って PNG を返す。
    channel_handle を指定するとファイル名に含まれ、複数チャンネルの衝突を防ぐ。
    """
    top_videos      = top_videos or []
    tailwind_js_src = _ensure_tailwind_cached()

    html_content = generate_html(
        channel_name=channel_name,
        report_date=report_date,
        subscribers=subscribers,
        subscriber_diff=subscriber_diff,
        daily_views=daily_views,
        comments=comments,
        top_videos=top_videos,
        tailwind_js_src=tailwind_js_src,
    )

    # ファイル名にチャンネルハンドルを含める（複数チャンネル対応）
    prefix = f"report_{channel_handle}_{report_date}" if channel_handle else f"report_{report_date}"

    html_path = os.path.join(REPORTS_DIR, f"{prefix}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    if save_path is None:
        save_path = os.path.join(REPORTS_DIR, f"{prefix}.png")

    _screenshot(html_path, save_path)
    return save_path


def _screenshot(html_path: str, png_path: str):
    """Playwright（同期版）で HTML をレンダリングして PNG として保存。"""
    from playwright.sync_api import sync_playwright

    html_url = Path(html_path).as_uri()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        try:
            page = browser.new_page(viewport={"width": 800, "height": 900})
            # ローカル JS キャッシュを優先。CDN の場合でも load まで待つ
            page.goto(html_url, wait_until="load", timeout=30_000)
            # Tailwind が DOM を解析してスタイルを適用する時間を確保
            page.wait_for_timeout(1200)
            page.screenshot(path=png_path, full_page=True)
        finally:
            browser.close()
