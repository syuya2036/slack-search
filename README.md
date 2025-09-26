# Slack Vector Bot (RAG minimal)


Slack のメッセージをベクトル化して検索できるボット。`uv` で依存管理、`src/` レイアウト。


## セットアップ
1. Slack App を作成（Socket Mode 有効化）し、以下スコープ例を付与 → ワークスペースに Install。
- `chat:write`, `channels:read`, `channels:history`, `groups:history`, `im:history`, `mpim:history`, `commands`
2. `.env` を用意（`.env.example` 参照）。
3. 依存インストール：
```bash
uv sync
```
4. 起動：
```bash
uv run slack-vector-bot
# もしくは
uv run python -m slack_vector_bot.main
```


### Slash コマンド
- `/ask <質問>` : ベクトル検索＋要約でリンクを返します。
- `/reindex` : `INDEX_CHANNELS` のバックフィル取り込み。


## 環境変数
- `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `SLACK_SIGNING_SECRET`, `OPENAI_API_KEY`
- `INDEX_CHANNELS` : 監視/バックフィル対象チャンネルID（カンマ区切り）
- （任意）`DB_PATH`, `INDEX_PATH`, `EMBED_MODEL`, `CHAT_MODEL`, `TOP_K_PER_QUERY`, `N_QUERY_AUG`, `MAX_RETURN`
