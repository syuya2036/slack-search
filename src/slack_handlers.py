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
from .llm import gen_search_queries, summarize_results

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
        if not question:
            respond(
                "質問を入力してください。例: `/ask 新プロダクトの発表はどのスレッド？`"
            )
            return
        try:
            queries = gen_search_queries(question)
            q_vecs = embed_texts(queries)
            cand: dict[int, float] = {}
            for i in range(q_vecs.shape[0]):
                D, I = store.search(q_vecs[i], TOP_K_PER_QUERY)
                for score, idx in zip(D.tolist(), I.tolist()):
                    if idx == -1:
                        continue
                    cand[idx] = max(cand.get(idx, -1e9), float(score))
            # 元質問で軽く再ランク（必要なら厳密な器用度に改修可）
            if cand:
                # FAISS index -> メッセージ取得
                faiss_indices = sorted(
                    cand.keys(), key=lambda k: cand[k], reverse=True
                )
                hits = store.fetch_meta_by_faiss_indices(
                    faiss_indices[:MAX_RETURN]
                )
                summary = summarize_results(question, hits)
                respond(summary)
            else:
                respond(
                    "該当が見つかりませんでした。インデックスの蓄積をお待ちください。"
                )
        except Exception as e:
            logger.exception(e)
            respond(f"検索中にエラーが発生しました: {e}")

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
