"""
Tailwind CSS を使ったレポート HTML を生成するモジュール。
Playwright でスクリーンショットを撮って PNG 画像に変換する。
"""
from __future__ import annotations

import html as _html
from datetime import date


def _e(text: str) -> str:
    return _html.escape(str(text), quote=True)


def _clean_comment(text: str) -> str:
    """YouTube API の textDisplay に含まれる <br> タグを改行に変換してエスケープする。"""
    import re
    # <br> / <br/> / <BR> などを改行に統一
    cleaned = re.sub(r"<br\s*/?>", "\n", str(text), flags=re.IGNORECASE)
    # その他の HTML タグを除去
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    return _html.escape(cleaned.strip(), quote=True)


def _diff_badge(diff: int | None) -> str:
    if diff is None:
        return '<span style="color:#888;font-size:13px;">（初回実行・前日データなし）</span>'
    if diff >= 0:
        return (
            f'<span style="color:#16a34a;font-weight:700;font-size:15px;">'
            f'▲ +{diff:,} 人　前日比</span>'
        )
    return (
        f'<span style="color:#dc2626;font-weight:700;font-size:15px;">'
        f'▼ {diff:,} 人　前日比</span>'
    )


def _video_rows(top_videos: list[dict]) -> str:
    if not top_videos:
        return '<p style="color:#aaa;text-align:center;padding:16px 0;">データなし（初回実行時は翌日から表示）</p>'

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    rows = []
    for i, v in enumerate(top_videos):
        rank  = i + 1
        title = _e(v.get("title", ""))
        thumb = _e(v.get("thumbnail", ""))
        views = v.get("daily_views", 0) or 0
        medal = medals.get(rank, str(rank))
        bg    = "#fffbeb" if rank == 1 else "#f8faff" if rank == 2 else "#fff8f5" if rank == 3 else "#fafafa"
        border = "#fbbf24" if rank == 1 else "#94a3b8" if rank == 2 else "#f97316" if rank == 3 else "#e5e7eb"

        rows.append(f"""
        <div style="display:flex;align-items:center;gap:10px;padding:8px 10px;
                    background:{bg};border:1px solid {border};border-radius:10px;margin-bottom:6px;">
          <div style="width:24px;text-align:center;font-size:16px;flex-shrink:0;">{medal}</div>
          <img src="{thumb}" style="width:120px;height:68px;object-fit:cover;border-radius:6px;
               background:#e5e7eb;flex-shrink:0;"
               onerror="this.style.background='#e5e7eb';this.removeAttribute('src')">
          <div style="flex:1;min-width:0;">
            <p style="margin:0;font-size:13px;font-weight:600;color:#1e293b;
                      overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;
                      -webkit-box-orient:vertical;">{title}</p>
            <p style="margin:4px 0 0;font-size:13px;font-weight:700;color:#16a34a;">{views:,} 回</p>
          </div>
        </div>
        """)
    return "\n".join(rows)


def _comment_rows(comments: list[dict]) -> str:
    if not comments:
        return '<p style="color:#aaa;text-align:center;padding:8px 0;font-size:13px;">昨日のコメントはありません</p>'

    rows = []
    for i, c in enumerate(comments):
        author = _e(c.get("author", "")[:16])
        text   = _clean_comment(c.get("text", "")).replace("\n", "<br>")
        bg     = "#f8fafc" if i % 2 == 0 else "#ffffff"
        rows.append(f"""
        <div style="display:flex;gap:6px;padding:7px 10px;border-radius:6px;background:{bg};">
          <span style="font-weight:700;font-size:12px;color:#334155;white-space:nowrap;flex-shrink:0;">{author}:</span>
          <span style="font-size:12px;color:#475569;">{text}</span>
        </div>
        """)
    return "\n".join(rows)


def generate_html(
    channel_name: str,
    report_date: date,
    subscribers: int,
    subscriber_diff: int | None,
    daily_views: int | None,
    comments: list[dict],
    top_videos: list[dict] | None = None,
    tailwind_js_src: str = "https://cdn.tailwindcss.com",
) -> str:
    top_videos   = top_videos or []
    channel_safe = _e(channel_name)

    weekdays = ["月", "火", "水", "木", "金", "土", "日"]
    wday     = weekdays[report_date.weekday()]
    date_str = f"{report_date.year}年{report_date.month}月{report_date.day}日（{wday}）"

    views_str    = f"{daily_views:,} 回" if (daily_views is not None and daily_views >= 0) else "—"
    diff_html    = _diff_badge(subscriber_diff)
    video_html   = _video_rows(top_videos)
    comment_html = _comment_rows(comments)
    n_comments   = len(comments)
    n_videos     = len(top_videos)

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=800">
  <title>YouTube 日次レポート</title>
  <style>
    * {{ font-family: 'Yu Gothic', 'YuGothic', 'Hiragino Sans', 'Meiryo', sans-serif;
         box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #ffffff; }}
  </style>
</head>
<body>
<div style="width:800px; background:#ffffff; padding:20px;">

  <!-- ═══ HEADER ═══ -->
  <div style="display:flex;align-items:center;gap:12px;
              background:#fff1f2;border:1px solid #fecdd3;
              border-radius:14px;padding:14px 18px;margin-bottom:14px;">
    <div style="width:40px;height:40px;background:#ff0000;border-radius:10px;
                display:flex;align-items:center;justify-content:center;flex-shrink:0;">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="white">
        <path d="M23.498 6.186a3.016 3.016 0 00-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 00.502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 002.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 002.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
      </svg>
    </div>
    <div>
      <h1 style="font-size:20px;font-weight:900;color:#1e293b;">YouTubeレポート</h1>
      <p style="font-size:12px;color:#64748b;margin-top:2px;">@{channel_safe}　•　{date_str}</p>
    </div>
  </div>

  <!-- ═══ STATS ROW ═══ -->
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:14px;">

    <!-- 登録者数 -->
    <div style="grid-column:1/4;background:#eff6ff;border:1px solid #bfdbfe;
                border-radius:14px;padding:16px 20px;">
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:8px;">
        <div style="width:26px;height:26px;background:#3b82f6;border-radius:50%;
                    display:flex;align-items:center;justify-content:center;">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="white">
            <path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/>
          </svg>
        </div>
        <span style="font-size:12px;font-weight:600;color:#2563eb;">チャンネル登録者数</span>
      </div>
      <div style="display:flex;align-items:flex-end;justify-content:space-between;">
        <div>
          <p style="font-size:48px;font-weight:900;color:#1e3a5f;line-height:1.1;">
            {subscribers:,} <span style="font-size:28px;color:#475569;">人</span>
          </p>
          <div style="margin-top:4px;">{diff_html}</div>
        </div>
      </div>
    </div>

    <!-- 昨日の再生数 -->
    <div style="grid-column:1/3;background:#f5f3ff;border:1px solid #ddd6fe;
                border-radius:14px;padding:14px 18px;">
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:8px;">
        <div style="width:26px;height:26px;background:#7c3aed;border-radius:50%;
                    display:flex;align-items:center;justify-content:center;">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="white"><path d="M8 5v14l11-7z"/></svg>
        </div>
        <span style="font-size:12px;font-weight:600;color:#6d28d9;">昨日の再生数（合計）</span>
      </div>
      <p style="font-size:36px;font-weight:900;color:#3b0764;">{views_str}</p>
    </div>

    <!-- コメント件数 -->
    <div style="background:#fff7ed;border:1px solid #fed7aa;
                border-radius:14px;padding:14px 18px;">
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:8px;">
        <div style="width:26px;height:26px;background:#ea580c;border-radius:50%;
                    display:flex;align-items:center;justify-content:center;">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="white">
            <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
          </svg>
        </div>
        <span style="font-size:12px;font-weight:600;color:#c2410c;">昨日のコメント</span>
      </div>
      <p style="font-size:36px;font-weight:900;color:#7c2d12;">{n_comments} <span style="font-size:20px;color:#92400e;">件</span></p>
    </div>
  </div>

  <!-- ═══ COMMENTS ═══ -->
  <div style="background:#fffbeb;border:1px solid #fde68a;border-radius:14px;
              padding:14px 16px;margin-bottom:14px;">
    <div style="display:flex;align-items:center;gap:6px;margin-bottom:10px;">
      <div style="width:24px;height:24px;background:#d97706;border-radius:50%;
                  display:flex;align-items:center;justify-content:center;">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="white">
          <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
        </svg>
      </div>
      <span style="font-size:13px;font-weight:700;color:#92400e;">昨日のコメント（{n_comments}件）</span>
    </div>
    <div style="max-height:600px;overflow-y:auto;">
    {comment_html}
    </div>
  </div>

  <!-- ═══ TOP VIDEOS ═══ -->
  <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:14px;padding:14px 16px;margin-bottom:14px;">
    <div style="display:flex;align-items:center;gap:6px;margin-bottom:10px;">
      <div style="width:24px;height:24px;background:#16a34a;border-radius:50%;
                  display:flex;align-items:center;justify-content:center;font-size:13px;">🏆</div>
      <span style="font-size:13px;font-weight:700;color:#14532d;">昨日の再生数 TOP {n_videos}（ショート除く）</span>
    </div>
    {video_html}
  </div>

  <!-- ═══ FOOTER ═══ -->
  <p style="text-align:center;font-size:11px;color:#94a3b8;padding:4px 0;">
    Powered by yt-line-reporter　•　毎日 12:00 自動送信
  </p>

</div>
</body>
</html>"""
