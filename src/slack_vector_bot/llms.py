from __future__ import annotations

from openai import OpenAI

from .config import CHAT_MODEL, N_QUERY_AUG, OPENAI_API_KEY

_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

_DEF_QUERY_SYS = "あなたはSlack検索支援です。ユーザ質問を、Slackの会話をヒットさせる短い検索クエリに言い換えてください。"

_DEF_SUM_SYS = "以下の候補から、ユーザ質問に最も関連するメッセージを要約し、関連順に最大10件『• 要約 — <リンク>』で列挙してください。"


def gen_search_queries(question: str, n: int = N_QUERY_AUG) -> list[str]:
    if _client is None:
        return [question]
    prompt = f"ユーザ質問: \n{question} \n\n{n}件の検索クエリを1行ずつ出力してください。"
    chat = _client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": _DEF_QUERY_SYS},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    text = chat.choices[0].message.content.strip()
    queries = [
        line.strip("- •	 ") for line in text.splitlines() if line.strip()
    ]
    return queries[:n] if queries else [question]


def summarize_results(question: str, hits: list[dict]) -> str:
    if _client is None or not hits:
        return "".join(
            [f"• <{h['permalink']}|リンク>: {h['text'][:120]}…" for h in hits]
        )
    context = "\n".join(
        [
            f"[{i+1}] user={h['user']} text={h['text']} link={h['permalink']}"
            for i, h in enumerate(hits)
        ]
    )
    user = f"ユーザ質問: {question} \n候補: \n{context}"
    chat = _client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": _DEF_SUM_SYS},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
    )
    return chat.choices[0].message.content.strip()
