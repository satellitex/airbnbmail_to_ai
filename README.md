# Airbnb Mail to AI

このプロジェクトは、Airbnbからのメール通知をGmailから取得し、内容を解析して外部サービスに情報を転送するPythonボットです。

## 機能概要

- Gmailから特定のAirbnbメール通知を自動取得
- メール内容を解析し、予約情報やゲストメッセージなどの重要情報を抽出
- 抽出した情報を指定された外部サービスに転送（APIやWebhookを利用）
- ログ記録と通知エラー処理

## 技術スタック

- Python 3.11+
- Poetry（パッケージ管理と仮想環境）
- Gmail API（メールアクセス用）
- 自然言語処理ライブラリ（メール内容解析用）
- 外部サービス連携用ライブラリ

## 開発環境セットアップ

このプロジェクトはモダンなPython開発ベストプラクティスに従っています。以下のツールを導入しています：

### 使用ツール一覧

| カテゴリ | 使用ツール | 目的 |
|----------|------------|------|
| パッケージ管理 | [Poetry](https://python-poetry.org) | 依存関係の管理と仮想環境の構築 |
| Linter | [Ruff](https://github.com/astral-sh/ruff) | 高速なlinter、formatter、import sorter |
| フォーマッター | Ruff (Blackモード) | 一貫したコードスタイル適用 |
| 型チェック | mypy | 静的型解析による型安全性確保 |
| テスト | pytest | ユニットテスト実行 |
| 開発補助 | pre-commit | コミット前の自動チェック |

### 環境構築手順

#### 前提条件

- Python 3.11以上がインストールされていること
- Gitがインストールされていること

#### セットアップ手順

1. **Poetryのインストール**

```bash
# Poetryのインストール
curl -sSL https://install.python-poetry.org | python3 -

# PATHの設定（bashの場合）
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# PATHの設定（zshの場合）
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# インストール確認
poetry --version
```

2. **プロジェクトのクローンとセットアップ**

```bash
# リポジトリのクローン
git clone https://github.com/yourusername/airbnmail_to_ai.git
cd airbnmail_to_ai

# 依存パッケージのインストール
poetry install

# 開発環境の有効化
poetry shell
```

3. **pre-commitフックのインストール**

```bash
# pre-commitのセットアップ
pre-commit install
```

4. **Gmail API認証情報の設定**

```bash
# 認証情報ファイルを credentials.json としてプロジェクトルートに配置
# (Google Cloud Consoleから取得したものを使用)

# トークン初期化の実行
poetry run python -m airbnmail_to_ai.auth.gmail_auth
```

## 使用方法

### 通常の実行モード

1. 設定ファイルの編集:

```bash
cp config.example.yaml config.yaml
# config.yamlを編集して設定を行う
```

2. ボットの実行:

```bash
# 直接実行
poetry run python -m airbnmail_to_ai

# または設定されたスケジュールでの実行
poetry run python -m airbnmail_to_ai --schedule
```

### CLIでの使用方法

このプロジェクトでは、`automated@airbnb.com`からのメールを取得・操作するためのコマンドラインインターフェース（CLI）が提供されています。

#### 基本的な使い方

```bash
# ヘルプの表示
poetry run airbnmail --help

# Gmail APIの認証
poetry run airbnmail auth

# メールの取得（デフォルトでは未読のautomated@airbnb.comからのメール）
poetry run airbnmail fetch

# 詳細なオプションの表示
poetry run airbnmail fetch --help
```

#### 認証方法

最初に認証を行う必要があります：

```bash
# デフォルトの認証情報ファイルを使用
poetry run airbnmail auth

# カスタム認証情報ファイルを指定
poetry run airbnmail auth --credentials path/to/credentials.json
```

#### メール検索のカスタマイズ

特定の検索クエリを使用してメールを取得：

```bash
# カスタム検索クエリを使用（Gmail検索構文）
poetry run airbnmail fetch --query "from:automated@airbnb.com subject:予約 after:2023/01/01"

# 取得するメール数を制限
poetry run airbnmail fetch --limit 5

# 取得後にメールを既読にマーク
poetry run airbnmail fetch --mark-read
```

#### 出力形式のカスタマイズ

```bash
# JSON形式で出力
poetry run airbnmail fetch --output json

# YAML形式で出力
poetry run airbnmail fetch --output yaml

# 結果をファイルに保存
poetry run airbnmail fetch --save results.txt
poetry run airbnmail fetch --output json --save results.json
```

#### メール内容の解析

```bash
# メール内容をAirbnb通知データとして解析
poetry run airbnmail fetch --parse
```

#### 使用例

1. 最新の5件のAirbnbメールを取得してJSONファイルに保存：
   ```bash
   poetry run airbnmail fetch --limit 5 --output json --save airbnb_emails.json
   ```

2. 特定期間の予約関連メールを検索して解析：
   ```bash
   poetry run airbnmail fetch --query "from:automated@airbnb.com subject:予約 after:2023/04/01 before:2023/05/01" --parse
   ```

3. すべての未読Airbnbメールを取得して既読にマーク：
   ```bash
   poetry run airbnmail fetch --mark-read
   ```

## テスト実行

```bash
# 全テストの実行
poetry run pytest

# カバレッジレポート付きでテスト実行
poetry run pytest --cov=airbnmail_to_ai
```

## プロジェクト構造

```
airbnmail_to_ai/
├── pyproject.toml          # Poetryの設定と依存関係
├── .pre-commit-config.yaml # pre-commitの設定
├── .gitignore              # Gitの除外ファイル設定
├── README.md               # このファイル
├── config.example.yaml     # 設定ファイルの例
├── src/
│   └── airbnmail_to_ai/    # メインパッケージ
│       ├── __init__.py
│       ├── __main__.py     # エントリーポイント
│       ├── auth/           # 認証関連
│       ├── gmail/          # Gmail API連携
│       ├── parser/         # メール解析
│       ├── models/         # データモデル
│       ├── services/       # 外部サービス連携
│       └── utils/          # ユーティリティ
└── tests/                  # テストコード
    ├── conftest.py
    ├── test_gmail.py
    ├── test_parser.py
    └── ...
```

## ライセンス

MIT

## 貢献について

プルリクエストや課題報告は歓迎します。大きな変更を加える前には、まず課題を提起して議論してください。
