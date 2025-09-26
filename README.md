# Slack Vector Bot (RAG minimal)

Slack のメッセージをベクトル化して検索できるボット。`uv` で依存管理、`src/` レイアウト。

# 手順書

# Slack Vector Bot セットアップ手順書

## 1. Slack App の作成

1. [Slack API: Your Apps](https://api.slack.com/apps) にアクセスし、 **Create New App** をクリック。
2. **From scratch** を選び、App 名とワークスペースを入力して作成。
3. **Basic Information → App-Level Tokens** に進み、`connections:write` スコープ付きの **App-Level Token** を作成（Socket Mode 用）。
   → `.env` の `SLACK_APP_TOKEN` にセット。

---

## 2. Bot Token の発行

1. 左メニュー **OAuth & Permissions** を開く。
2. **Scopes → Bot Token Scopes** に以下を追加：

   - `chat:write`
   - `commands`
   - `channels:read`
   - `channels:history`
   - `groups:history`
   - `im:history`
   - `mpim:history`

3. **Install App to Workspace** をクリックして承認。
   発行される **Bot User OAuth Token (xoxb-)** を `.env` の `SLACK_BOT_TOKEN` にセット。

---

## 3. Signing Secret の確認

1. **Basic Information → App Credentials** で **Signing Secret** をコピー。
2. `.env` の `SLACK_SIGNING_SECRET` にセット。

---

## 4. Slash コマンドの設定

1. **Slash Commands** を開き、次のコマンドを追加：

   - `/ask` → Request URL は一旦ダミー（例: [https://example.com/ask）](https://example.com/ask）)
   - `/reindex` → 同様にダミー URL

2. 実際は **Socket Mode** で処理するため、Request URL は動作しなくても OK。
3. Socket Mode を有効化（**Settings → Socket Mode**）。
   - **App-Level Token** は前ステップで作成したものを使用。

---

## 5. OpenAI API キー取得

1. [OpenAI API Keys](https://platform.openai.com/account/api-keys) から新規キーを発行。
2. `.env` の `OPENAI_API_KEY` にセット。

---

## 6. `.env` 設定例

```dotenv
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SLACK_SIGNING_SECRET=...
OPENAI_API_KEY=sk-...

# オプション
INDEX_CHANNELS=C0123ABC,C0456DEF
DB_PATH=messages.db
INDEX_PATH=index.faiss
```

---

## 7. プロジェクト起動

1. 依存インストール

   ```bash
   uv sync
   ```

2. 実行

   ```bash
   uv run slack-vector-bot
   ```

   または

   ```bash
   uv run python -m slack_vector_bot.main
   ```

---

## 8. 動作確認

- Slack で `/ask 最近のリリース情報` と入力
  → 関連メッセージのリンクが返る
- Slack で `/reindex` と入力
  → `INDEX_CHANNELS` のメッセージをまとめて取り込み

---

## 9. 運用メモ

- **初回**は `/reindex` でバックフィルしないと検索対象が少ない。
- 権限は必要最小限で運用（DM も拾うなら `im:history` が必須）。
- SQLite/FAISS の永続化は `.db` `.faiss` を永続ボリュームや S3 に保存推奨。
