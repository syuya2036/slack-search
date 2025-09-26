from __future__ import annotations

from slack_sdk import WebClient

from .config import (
    DB_PATH,
    INDEX_CHANNELS,
    INDEX_PATH,
    MAX_RETURN,
    SLACK_BOT_TOKEN,
    TOP_K_PER_QUERY,
)
from .db import MessageStore
from .embeddings import embed_texts
from .llms import gen_search_queries, summarize_results

store = MessageStore(DB_PATH, INDEX_PATH)
client = WebClient(token=SLACK_BOT_TOKEN)


def register_handlers(app):
    @app.event("message")
    def handle_message_events(body, logger):
        event = body.get("event", {})
        subtype = event.get("subtype")
        if subtype in {
            "message_changed",
            "message_deleted",
            "bot_message",
            "channel_join",
            "channel_leave",
        }:
            return
        channel = event.get("channel")
        user = event.get("user", "")
        text = (event.get("text") or "").strip()
        ts = event.get("ts")
        if not text or not ts or not channel:
            return
        try:
            permalink = client.chat_getPermalink(
                channel=channel, message_ts=ts
            ).get("permalink", "")
            emb = embed_texts([text])[0]
            store.upsert_message(channel, ts, user, text, permalink, emb)
        except Exception as e:
            logger.error(f"index error: {e}")

    @app.command("/ask")
    def ask_command(ack, respond, command, logger):
        ack()
        question = (command.get("text") or "").strip()
        channel_id = command.get("channel_id")
        user_id = command.get("user_id")

        if not question:
            respond(
                "質問を入力してください。例: `/ask 新プロダクトの発表はどのスレッド？`"
            )
            return

        # 1) プレースホルダーを投稿（生成中表示 + 質問は残す）
        placeholder_text = f":mag: *検索中…*  <@{user_id}>\n> {question}"
        try:
            ph = client.chat_postMessage(
                channel=channel_id, text=placeholder_text
            )
            ph_ts = ph["ts"]
        except SlackApiError as e:
            logger.error(f"placeholder error: {e.response}")
            respond(f"検索開始に失敗しました: {e.response.get('error')}")
            return

        try:
            # 2) RAG 検索
            queries = gen_search_queries(question)
            q_vecs = embed_texts(queries)
            cand: dict[int, float] = {}
            for i in range(q_vecs.shape[0]):
                D, I = store.search(q_vecs[i], TOP_K_PER_QUERY)
                for score, idx in zip(D.tolist(), I.tolist()):
                    if idx == -1:
                        continue
                    cand[idx] = max(cand.get(idx, -1e9), float(score))

            hits = []
            if cand:
                faiss_indices = sorted(
                    cand.keys(), key=lambda k: cand[k], reverse=True
                )
                hits = store.fetch_meta_by_faiss_indices(
                    faiss_indices[:MAX_RETURN]
                )

            summary = (
                summarize_results(question, hits)
                if hits
                else "該当が見つかりませんでした。"
            )

            # 3) ログ保存
            store.log_query(
                channel_id=channel_id,
                user_id=user_id,
                question=question,
                result_count=len(hits),
            )

            # 4) プレースホルダーを「結果」に更新（質問は残す）
            final_text = f":white_check_mark: *検索結果*  <@{user_id}>\n> {question}\n\n{summary}"
            client.chat_update(channel=channel_id, ts=ph_ts, text=final_text)

        except Exception as e:
            logger.exception(e)
            # エラー時はプレースホルダーをエラー表示に更新
            err_text = f":warning: *検索でエラーが発生しました*\n> {question}\n\n`{e}`"
            try:
                client.chat_update(channel=channel_id, ts=ph_ts, text=err_text)
            except Exception:
                pass

    @app.command("/reindex")
    def reindex_command(ack, respond, command, logger):
        ack()
        if not INDEX_CHANNELS:
            respond("INDEX_CHANNELS が未設定です。")
            return
        total = 0
        try:
            for ch in INDEX_CHANNELS:
                latest = None
                for _ in range(10):  # 最大 ~1000件/チャンネル
                    resp = client.conversations_history(
                        channel=ch, limit=100, latest=latest
                    )
                    messages = resp.get("messages", [])
                    if not messages:
                        break
                    for m in messages:
                        if m.get("subtype"):
                            continue
                        text = (m.get("text") or "").strip()
                        ts = m.get("ts")
                        user = m.get("user", "")
                        if not text or not ts:
                            continue
                        permalink = client.chat_getPermalink(
                            channel=ch, message_ts=ts
                        ).get("permalink", "")
                        emb = embed_texts([text])[0]
                        store.upsert_message(
                            ch, ts, user, text, permalink, emb
                        )
                        total += 1
                    latest = messages[-1]["ts"]
            respond(f"バックフィル完了: 追加 {total} 件")
        except Exception as e:
            logger.error(f"reindex error: {e}")
            respond(f"バックフィル中にエラーが発生しました: {e}")
