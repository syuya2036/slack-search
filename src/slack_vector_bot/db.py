# src/slack_vector_bot/db.py
from __future__ import annotations

import os
import sqlite3
import threading
from typing import Dict, List, Tuple

import faiss
import numpy as np

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    user TEXT,
    text TEXT,
    permalink TEXT,
    embedding_dim INTEGER NOT NULL,
    UNIQUE(channel_id, ts)
);
CREATE TABLE IF NOT EXISTS vector_map (
    message_id INTEGER UNIQUE,
    faiss_id   INTEGER UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_vector_map_faiss ON vector_map(faiss_id);
"""


class MessageStore:
    def __init__(self, db_path: str, index_path: str):
        self.db_path = db_path
        self.index_path = index_path

        # スキーマ初期化は1回だけ専用コネクションで
        _init_conn = sqlite3.connect(self.db_path, check_same_thread=False)
        _init_conn.execute("PRAGMA journal_mode=WAL;")
        _init_conn.executescript(SCHEMA_SQL)
        _init_conn.commit()
        _init_conn.close()

        # スレッドローカルコネクション & ロック
        self._local = threading.local()
        self._db_lock = threading.RLock()
        self._index_lock = threading.RLock()

        self.index = self._load_or_create_index()

    # -------- SQLite helpers (per-thread connection) --------
    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn"):
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL;")
            # 速度と安全性のバランス（必要に応じて調整）
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA temp_store=MEMORY;")
            self._local.conn = conn
        return self._local.conn

    # -------- FAISS index I/O --------
    def _load_or_create_index(self):
        with self._index_lock:
            if os.path.exists(self.index_path):
                return faiss.read_index(self.index_path)
            return None

    def _init_index(self, dim: int):
        with self._index_lock:
            self.index = faiss.IndexFlatIP(dim)
            self._save_index()

    def _save_index(self):
        with self._index_lock:
            if self.index is not None:
                faiss.write_index(self.index, self.index_path)

    # -------- writes --------
    def upsert_message(
        self,
        channel_id: str,
        ts: str,
        user: str,
        text: str,
        permalink: str,
        embedding: np.ndarray,
    ) -> int:
        conn = self._conn()
        with self._db_lock:
            cur = conn.cursor()
            cur.execute(
                "INSERT OR IGNORE INTO messages(channel_id, ts, user, text, permalink, embedding_dim) VALUES(?,?,?,?,?,?)",
                (
                    channel_id,
                    ts,
                    user,
                    text,
                    permalink,
                    int(embedding.shape[0]),
                ),
            )
            conn.commit()

            cur.execute(
                "SELECT id, embedding_dim FROM messages WHERE channel_id=? AND ts=?",
                (channel_id, ts),
            )
            row = cur.fetchone()
            if not row:
                raise RuntimeError("failed to fetch inserted message row")
            msg_id = int(row[0])
            dim = int(row[1]) if row[1] else embedding.shape[0]

            # ベクトルマップに既存ならFAISS追加はスキップ
            cur.execute(
                "SELECT faiss_id FROM vector_map WHERE message_id=?", (msg_id,)
            )
            if cur.fetchone() is not None:
                return msg_id

        # ---- FAISS add（ロックで直列化）----
        if self.index is None:
            self._init_index(dim)
        if self.index.d != embedding.shape[0]:
            raise ValueError(
                f"Embedding dim mismatch: index={self.index.d}, vec={embedding.shape[0]}"
            )

        vec = embedding.astype(np.float32).reshape(1, -1)
        faiss.normalize_L2(vec)
        with self._index_lock:
            current = self.index.ntotal
            self.index.add(vec)
            self._save_index()

        # マッピング登録はDBロックで
        with self._db_lock:
            cur = self._conn().cursor()
            cur.execute(
                "INSERT OR IGNORE INTO vector_map(message_id, faiss_id) VALUES(?, ?)",
                (msg_id, current),
            )
            self._conn().commit()
        return msg_id

    # -------- reads --------
    def search(
        self, query_vec: np.ndarray, k: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        if self.index is None or self.index.ntotal == 0:
            return np.array([]), np.array([])
        vec = query_vec.astype(np.float32).reshape(1, -1)
        faiss.normalize_L2(vec)
        with self._index_lock:
            D, I = self.index.search(vec, k)
        return D[0], I[0]

    def fetch_meta_by_faiss_indices(
        self, faiss_indices: List[int]
    ) -> List[Dict]:
        if not faiss_indices:
            return []
        items: List[Dict] = []
        with self._db_lock:
            cur = self._conn().cursor()
            for fid in faiss_indices:
                cur.execute(
                    "SELECT m.id, m.channel_id, m.ts, m.user, m.text, m.permalink "
                    "FROM vector_map vm JOIN messages m ON vm.message_id = m.id "
                    "WHERE vm.faiss_id = ?",
                    (int(fid),),
                )
                row = cur.fetchone()
                if row:
                    items.append(
                        {
                            "id": int(row[0]),
                            "channel_id": row[1],
                            "ts": row[2],
                            "user": row[3],
                            "text": row[4],
                            "permalink": row[5],
                        }
                    )
        return items
