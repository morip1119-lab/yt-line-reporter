"""
LINE Messaging API を使ってグループに画像を送信するモジュール。
画像は外部サービスに一時アップロードして公開 URL を取得してから送信する。
複数グループへの同時送信に対応。
"""
from __future__ import annotations

import logging

import requests

from config import LINE_CHANNEL_ACCESS_TOKEN

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.line.me/v2/bot"


def _headers():
    return {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


def _upload_image(image_path: str) -> str:
    """
    複数のホスティングサービスを順番に試して公開 HTTPS URL を返す。
    LINE サーバーからアクセスできる URL が必要。
    """
    providers = [_try_0x0, _try_litterbox]
    last_err = None
    for fn in providers:
        try:
            url = fn(image_path)
            logger.info("画像アップロード完了 (%s): %s", fn.__name__, url)
            return url
        except Exception as e:
            logger.warning("%s 失敗: %s", fn.__name__, e)
            last_err = e
    raise RuntimeError(f"全ての画像アップロード先で失敗しました: {last_err}")


def _try_0x0(image_path: str) -> str:
    with open(image_path, "rb") as f:
        resp = requests.post(
            "https://0x0.st",
            files={"file": ("report.png", f, "image/png")},
            timeout=60,
        )
    resp.raise_for_status()
    url = resp.text.strip()
    if not url.startswith("https://"):
        raise ValueError(f"予期しないレスポンス: {url}")
    return url


def _try_litterbox(image_path: str) -> str:
    with open(image_path, "rb") as f:
        resp = requests.post(
            "https://litterbox.catbox.moe/resources/internals/api.php",
            data={"reqtype": "fileupload", "time": "72h"},
            files={"fileToUpload": ("report.png", f, "image/png")},
            timeout=60,
        )
    resp.raise_for_status()
    url = resp.text.strip()
    if not url.startswith("https://"):
        raise ValueError(f"予期しないレスポンス: {url}")
    return url


def send_image_to_group(image_path: str, group_ids: list[str]) -> list[dict]:
    """
    画像を公開ホストにアップロードし、指定した全 LINE グループに送信する。
    group_ids が空の場合は何もしない。
    """
    if not group_ids:
        logger.warning("送信先グループ ID が設定されていません")
        return []

    image_url = _upload_image(image_path)

    results = []
    for group_id in group_ids:
        body = {
            "to": group_id,
            "messages": [
                {
                    "type": "image",
                    "originalContentUrl": image_url,
                    "previewImageUrl":    image_url,
                }
            ],
        }
        res = requests.post(
            f"{_BASE_URL}/message/push",
            headers=_headers(),
            json=body,
            timeout=30,
        )
        res.raise_for_status()
        results.append(res.json())
        logger.info("LINE 送信完了 → グループ %s", group_id)

    return results


def send_text_to_group(text: str, group_ids: list[str]) -> list[dict]:
    """テキストメッセージを複数グループに送信（デバッグ用）。"""
    results = []
    for group_id in group_ids:
        body = {
            "to": group_id,
            "messages": [{"type": "text", "text": text}],
        }
        res = requests.post(
            f"{_BASE_URL}/message/push",
            headers=_headers(),
            json=body,
            timeout=30,
        )
        res.raise_for_status()
        results.append(res.json())
    return results


def verify_credentials() -> tuple[bool, str]:
    """トークンの簡易チェック。"""
    if not LINE_CHANNEL_ACCESS_TOKEN:
        return False, "LINE_CHANNEL_ACCESS_TOKEN が設定されていません"
    res = requests.get(
        f"{_BASE_URL}/info",
        headers=_headers(),
        timeout=10,
    )
    if res.status_code == 200:
        bot_name = res.json().get("displayName", "")
        return True, f"Bot 名: {bot_name}"
    return False, f"認証エラー: {res.status_code} {res.text}"
