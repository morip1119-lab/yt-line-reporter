"""
GitHub Actions から呼び出す定期実行スクリプト。
Streamlit なしで全チャンネルのレポートを生成・送信する。
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from config import CHANNELS
import runner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")


def main():
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST")
    logger.info("=== レポート実行開始 %s ===", now)

    if not CHANNELS:
        logger.error("チャンネルが設定されていません。環境変数を確認してください。")
        sys.exit(1)

    all_ok = True
    for ch in CHANNELS:
        logger.info("--- @%s 処理開始 ---", ch["handle"])
        result = runner.run_report(ch, send_to_line=True)

        if result["success"]:
            logger.info(
                "@%s 完了: 登録者=%s 再生=%s コメント=%s件",
                ch["handle"],
                f"{result['subscribers']:,}",
                f"{result['daily_views']:,}" if result["daily_views"] is not None else "N/A",
                len(result["comments"]),
            )
            if result["line_sent"]:
                logger.info("  → LINE 送信完了（%d グループ）", result.get("groups_sent", 0))
            elif result.get("warning"):
                logger.warning("  → %s", result["warning"])
        else:
            logger.error("@%s エラー: %s", ch["handle"], result["error"])
            all_ok = False

    if all_ok:
        logger.info("=== 全チャンネル完了 ===")
    else:
        logger.error("=== 一部チャンネルでエラーが発生しました ===")
        sys.exit(1)


if __name__ == "__main__":
    main()
