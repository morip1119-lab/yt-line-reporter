# yt-line-reporter

YouTube チャンネルの日次レポートを画像生成し、LINE グループへ自動送信するツールです。

## 完成イメージ

![レポートイメージ](assets/report_mockup.png)

## 機能

- 毎日 12:00 に自動でレポートを送信
- ダッシュボード UI から手動でも実行可能
- 取得データ:
  - 現在の登録者数
  - 前日との登録者数増減
  - 昨日の再生数（前日からの差分）
  - 昨日届いたコメント（最大5件）
- レポートを画像として生成し LINE グループへ送信

---

## セットアップ手順

### 1. Python 環境の準備

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Mac/Linux

pip install -r requirements.txt

# Playwright のブラウザ本体をインストール（初回のみ）
playwright install chromium
```

### 2. API キーの取得

#### YouTube Data API v3

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. 新しいプロジェクトを作成
3. 「APIとサービス」→「ライブラリ」→「YouTube Data API v3」を有効化
4. 「認証情報」→「APIキーを作成」

#### LINE Messaging API

1. [LINE Developers Console](https://developers.line.biz/) にアクセス
2. 「新しいチャンネルを作成」→「Messaging API」を選択
3. チャンネルアクセストークン（長期）を発行
4. 作成した Bot をレポート送信先の **LINE グループに追加**
5. グループ ID の確認:
   - Bot の Webhook URL を設定し、グループでメッセージを送ると `source.groupId` が取得できます
   - または [LINE Group ID 確認ツール](https://line.me/R/ti/p/@your-bot-id) を使用

### 3. 環境変数の設定

```bash
cp .env.example .env
```

`.env` を開いて各値を設定:

```env
YOUTUBE_API_KEY=AIza...          # YouTube API キー
YOUTUBE_CHANNEL_HANDLE=marketing-zamurai
LINE_CHANNEL_ACCESS_TOKEN=...    # LINE チャンネルアクセストークン
LINE_GROUP_ID=C...               # LINE グループ ID
REPORT_TIME=12:00                # 送信時刻（24時間表記）
```

### 4. 起動

```bash
streamlit run main.py
```

ブラウザで `http://localhost:8501` が自動的に開きます。

---

## 使い方

### ダッシュボード

- 最新レポート画像のプレビューが表示されます
- **「▶ 今すぐ実行」** ボタンでレポートを手動生成・送信
- 「LINE グループへ送信する」チェックを外すと画像生成のみ（送信しない）

### 自動送信

- アプリ起動中、毎日 `REPORT_TIME`（デフォルト 12:00）に自動送信されます
- **PC を起動したままアプリを起動しておく必要があります**
- 「設定・確認」ページでスケジューラーのログを確認できます

### 設定・確認ページ

- API キーの設定状況確認
- LINE Bot の接続テスト
- YouTube チャンネルの接続テスト

---

## 注意事項

- YouTube Data API には **1日あたりの無料クォータ制限**（10,000 ユニット）があります
  - `channels.list`: 1回あたり約1ユニット
  - `commentThreads.list`: 1回あたり約1ユニット
  - 1日1回の実行であれば問題ありません
- 「昨日の再生数」は前日の合計再生数との差分で算出します（初回実行時は「データなし」と表示）

---

## ファイル構成

```
yt-line-reporter/
├── main.py              # Streamlit UI・スケジューラー
├── runner.py            # レポート実行ロジック
├── youtube_api.py       # YouTube Data API ラッパー
├── report_generator.py  # Pillow による画像生成
├── line_api.py          # LINE Messaging API ラッパー
├── data_store.py        # SQLite によるデータ管理
├── config.py            # 設定読み込み
├── requirements.txt
├── .env.example
├── .gitignore
└── data/                # 自動生成
    ├── stats.db         # 統計データ（SQLite）
    └── reports/         # 生成済みレポート画像
```
