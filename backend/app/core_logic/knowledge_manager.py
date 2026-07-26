import asyncio
import json
import math
import os
import re
import sqlite3  # only used for sync schema init (__init__)
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional, Set, Tuple

import aiosqlite

from .sqlite_pool import SQLiteConnectionPool


class KnowledgeManager:
    MEMORY_TAG_RE = re.compile(r"^\[memory\s+.*?\]\s*", re.I | re.S)
    TOKEN_RE = re.compile(r"[0-9A-Za-z_\u4e00-\u9fff]+")

    POLICY_DEFAULTS: Dict[str, Any] = {
        "auto_memory_enabled": True,
        "auto_memory_min_length": 8,
        "auto_memory_cooldown_seconds": 45,
        "auto_memory_promote_min_observations": 2,
        "auto_memory_promote_min_distinct_users": 1,
        "auto_memory_quality_threshold": 0.55,
        "auto_memory_direct_promote_ai_tag": False,
        "auto_memory_recall_top_k": 12,
        "auto_memory_recall_char_limit": 2200,
        "auto_memory_recall_max_age_days": 365,
    }

    def __init__(self, db_path: Optional[str] = None, pool_max_connections: int = 10, pool_idle_timeout: float = 300.0):
        if db_path is None:
            db_dir = "data"
            os.makedirs(db_dir, exist_ok=True)
            self.db_path = os.path.join(db_dir, "knowledge_base.sqlite")
        else:
            self.db_path = db_path
        self._pool = SQLiteConnectionPool(
            self.db_path,
            max_connections=pool_max_connections,
            idle_timeout=pool_idle_timeout,
        )
        # Schema init is sync using a temporary raw sqlite3 connection.
        self._init_db_sync()

    # ------------------------------------------------------------------
    # Sync schema initialisation (runs once in __init__)
    # ------------------------------------------------------------------

    def _init_db_sync(self) -> None:
        """Initialise the database schema synchronously.

        Uses a one-off ``sqlite3`` connection so that ``__init__`` can
        remain a plain (non-async) constructor.
        """
        scripts_dir = "/app/scripts"
        if not os.path.isdir(scripts_dir):
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            scripts_dir = os.path.join(base_dir, "scripts")
        init_script_path = os.path.join(scripts_dir, "1_initialize_schema.sql")
        if not os.path.exists(init_script_path):
            print(f"CRITICAL: Database initialization script not found at {init_script_path}")
            return

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            with open(init_script_path, "r", encoding="utf-8") as f:
                conn.executescript(f.read())
            self._ensure_runtime_schema(conn.cursor())
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_runtime_schema(self, cursor: sqlite3.Cursor) -> None:
        cursor.execute("PRAGMA table_info(memory_candidates)")
        cols = {row[1] for row in cursor.fetchall()}
        if cols:
            if "last_user_id" not in cols:
                cursor.execute("ALTER TABLE memory_candidates ADD COLUMN last_user_id TEXT")
            if "last_user_name" not in cols:
                cursor.execute("ALTER TABLE memory_candidates ADD COLUMN last_user_name TEXT")

        cursor.execute("PRAGMA table_info(memory)")
        memory_cols = {row[1] for row in cursor.fetchall()}
        if memory_cols and "normalized_content" not in memory_cols:
            cursor.execute("ALTER TABLE memory ADD COLUMN normalized_content TEXT")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_normalized_content ON memory(normalized_content)")
        if memory_cols and "embedding" not in memory_cols:
            cursor.execute("ALTER TABLE memory ADD COLUMN embedding BLOB")

    # ------------------------------------------------------------------
    # Async connection pool access
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def get_conn(self) -> AsyncIterator[aiosqlite.Connection]:
        async with self._pool.acquire() as conn:
            yield conn

    # ------------------------------------------------------------------
    # Pure helpers (unchanged, sync)
    # ------------------------------------------------------------------

    def _safe_int(self, value: Any, default: int, lo: int, hi: int) -> int:
        try:
            return max(lo, min(hi, int(value)))
        except (TypeError, ValueError):
            return default

    def _safe_float(self, value: Any, default: float, lo: float, hi: float) -> float:
        try:
            return max(lo, min(hi, float(value)))
        except (TypeError, ValueError):
            return default

    def _safe_bool(self, value: Any, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            v = value.strip().lower()
            if v in {"1", "true", "yes", "on"}:
                return True
            if v in {"0", "false", "no", "off"}:
                return False
        return default

    def _resolve_policy(self, config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        cfg = config if isinstance(config, dict) else {}
        d = self.POLICY_DEFAULTS
        return {
            "auto_memory_enabled": self._safe_bool(cfg.get("auto_memory_enabled"), d["auto_memory_enabled"]),
            "auto_memory_min_length": self._safe_int(cfg.get("auto_memory_min_length"), d["auto_memory_min_length"], 0, 500),
            "auto_memory_cooldown_seconds": self._safe_int(cfg.get("auto_memory_cooldown_seconds"), d["auto_memory_cooldown_seconds"], 0, 3600),
            "auto_memory_promote_min_observations": self._safe_int(cfg.get("auto_memory_promote_min_observations"), d["auto_memory_promote_min_observations"], 1, 50),
            "auto_memory_promote_min_distinct_users": self._safe_int(cfg.get("auto_memory_promote_min_distinct_users"), d["auto_memory_promote_min_distinct_users"], 1, 50),
            "auto_memory_quality_threshold": self._safe_float(cfg.get("auto_memory_quality_threshold"), d["auto_memory_quality_threshold"], 0.0, 1.0),
            "auto_memory_direct_promote_ai_tag": self._safe_bool(cfg.get("auto_memory_direct_promote_ai_tag"), d["auto_memory_direct_promote_ai_tag"]),
            "auto_memory_recall_top_k": self._safe_int(cfg.get("auto_memory_recall_top_k"), d["auto_memory_recall_top_k"], 1, 50),
            "auto_memory_recall_char_limit": self._safe_int(cfg.get("auto_memory_recall_char_limit"), d["auto_memory_recall_char_limit"], 300, 20000),
            "auto_memory_recall_max_age_days": self._safe_int(cfg.get("auto_memory_recall_max_age_days"), d["auto_memory_recall_max_age_days"], 1, 3650),
        }

    def _strip_tag(self, content: str) -> str:
        return self.MEMORY_TAG_RE.sub("", str(content or "")).strip()

    def _normalize(self, content: str) -> str:
        return re.sub(r"\s+", " ", self._strip_tag(content).lower()).strip()

    def _tokens(self, text: str, max_tokens: int = 20) -> List[str]:
        out: List[str] = []
        seen = set()
        for raw in self.TOKEN_RE.findall((text or "").lower()):
            t = raw.strip()
            if len(t) < 2 or t in seen:
                continue
            seen.add(t)
            out.append(t)
            if len(out) >= max_tokens:
                break
        return out

    def _dt(self, ts: Optional[str]) -> datetime:
        if not ts:
            return datetime.now(timezone.utc)
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            return datetime.now(timezone.utc)

    def _set_from_json(self, raw: Optional[str]) -> Set[str]:
        if not raw:
            return set()
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return {str(x) for x in data if str(x).strip()}
        except json.JSONDecodeError:
            pass
        return set()

    def _set_json(self, values: Set[str]) -> str:
        return json.dumps(sorted(values), ensure_ascii=False)

    def _low_signal(self, content: str) -> bool:
        text = (content or "").strip()
        if not text:
            return True
        if re.fullmatch(r"https?://\S+", text):
            return True
        if re.fullmatch(r"<@!?\d+>", text):
            return True
        if not re.search(r"[0-9A-Za-z\u4e00-\u9fff]", text):
            return True
        return False

    def _quality_score(self, content: str, seen_count: int, distinct_users: int, p: Dict[str, Any]) -> float:
        target_len = max(8, int(p["auto_memory_min_length"]) * 4)
        s_len = min(1.0, len(content) / target_len)
        s_seen = min(1.0, seen_count / max(1, int(p["auto_memory_promote_min_observations"])))
        s_users = min(1.0, distinct_users / max(1, int(p["auto_memory_promote_min_distinct_users"])))
        s_clean = 0.0 if self._low_signal(content) else 1.0
        return max(0.0, min(1.0, 0.25 * s_len + 0.35 * s_seen + 0.25 * s_users + 0.15 * s_clean))

    # ------------------------------------------------------------------
    # Async DB helpers
    # ------------------------------------------------------------------

    async def _find_existing_memory(self, normalized: str) -> Optional[int]:
        async with self.get_conn() as conn:
            c = await conn.cursor()
            await c.execute(
                "SELECT promoted_memory_id FROM memory_candidates WHERE normalized_content=? AND promoted=1 AND promoted_memory_id IS NOT NULL LIMIT 1",
                (normalized,),
            )
            row = await c.fetchone()
            if row and row["promoted_memory_id"]:
                return int(row["promoted_memory_id"])
            await c.execute("SELECT id FROM memory WHERE normalized_content = ? LIMIT 1", (normalized,))
            row = await c.fetchone()
            if row:
                return int(row["id"])
        return None

    # ------------------------------------------------------------------
    # Memory CRUD
    # ------------------------------------------------------------------

    async def add_memory(self, content: str, timestamp: str, user_id: str, user_name: str, source: str) -> Optional[int]:
        try:
            safe_user = (user_name or "Unknown").replace('"', '""')
            tag = f'[memory timestamp="{timestamp}" source="{source}" user_name="{safe_user}" user_id="{user_id}"]'
            tagged_content = f"{tag} {content}".strip()
            normalized = self._normalize(content)
            async with self.get_conn() as conn:
                c = await conn.cursor()
                await c.execute(
                    "INSERT INTO memory (content, normalized_content, timestamp, user_id, user_name, source) VALUES (?, ?, ?, ?, ?, ?)",
                    (tagged_content, normalized, timestamp, user_id, user_name, source),
                )
                memory_id = c.lastrowid
                await c.execute(
                    "INSERT INTO memory_stats (memory_id, recall_count, last_recalled_at, last_recall_score) VALUES (?, 0, NULL, 0) ON CONFLICT(memory_id) DO NOTHING",
                    (memory_id,),
                )
                if normalized:
                    await c.execute(
                        """
                        INSERT INTO memory_candidates (
                            normalized_content, content_sample, first_seen, last_seen, seen_count, distinct_user_count,
                            last_user_id, last_user_name, user_ids_json, channel_ids_json, source_types_json, promoted,
                            promoted_memory_id, promoted_at, last_reason
                        ) VALUES (?, ?, ?, ?, 1, 1, ?, ?, ?, '[]', ?, 1, ?, ?, ?)
                        ON CONFLICT(normalized_content) DO UPDATE SET
                            content_sample = excluded.content_sample,
                            last_seen = excluded.last_seen,
                            last_user_id = excluded.last_user_id,
                            last_user_name = excluded.last_user_name,
                            source_types_json = excluded.source_types_json,
                            promoted = 1,
                            promoted_memory_id = excluded.promoted_memory_id,
                            promoted_at = excluded.promoted_at,
                            last_reason = excluded.last_reason
                        """,
                        (
                            normalized,
                            self._strip_tag(content),
                            timestamp,
                            timestamp,
                            str(user_id or "unknown_user"),
                            str(user_name or "Unknown"),
                            self._set_json({str(user_id or "unknown_user")}),
                            self._set_json({str(source or "unknown")}),
                            memory_id,
                            datetime.now(timezone.utc).isoformat(),
                            "direct_add_promoted",
                        ),
                    )
                await conn.commit()
                return memory_id
        except aiosqlite.IntegrityError:
            return None

    async def ingest_memory_candidate(
        self,
        content: str,
        timestamp: str,
        user_id: str,
        user_name: str,
        source: str,
        config: Optional[Dict[str, Any]] = None,
        channel_id: Optional[str] = None,
        force_promote: bool = False,
    ) -> Dict[str, Any]:
        p = self._resolve_policy(config)
        cleaned = self._strip_tag(content)
        normalized = self._normalize(cleaned)
        if not normalized:
            return {"status": "skipped_empty"}
        if not p["auto_memory_enabled"] and not force_promote:
            return {"status": "skipped_disabled"}
        if len(cleaned) < int(p["auto_memory_min_length"]):
            return {"status": "skipped_too_short"}
        if self._low_signal(cleaned):
            return {"status": "skipped_low_signal"}
        existing_id = await self._find_existing_memory(normalized)
        if existing_id:
            return {"status": "duplicate_existing", "memory_id": existing_id}

        now = self._dt(timestamp)
        now_ts = now.isoformat()
        uid = str(user_id or "unknown_user")
        cid = str(channel_id) if channel_id is not None else ""

        async with self.get_conn() as conn:
            c = await conn.cursor()
            await c.execute("SELECT * FROM memory_candidates WHERE normalized_content=? LIMIT 1", (normalized,))
            row = await c.fetchone()
            if row:
                candidate = dict(row)
                elapsed = (now - self._dt(candidate.get("last_seen"))).total_seconds()
                if (
                    int(p["auto_memory_cooldown_seconds"]) > 0
                    and candidate.get("last_user_id") == uid
                    and elapsed < int(p["auto_memory_cooldown_seconds"])
                    and not force_promote
                ):
                    return {"status": "cooldown", "candidate_id": candidate["id"]}
                users = self._set_from_json(candidate.get("user_ids_json"))
                sources = self._set_from_json(candidate.get("source_types_json"))
                channels = self._set_from_json(candidate.get("channel_ids_json"))
                users.add(uid)
                sources.add(str(source or "unknown"))
                if cid:
                    channels.add(cid)
                seen_count = int(candidate.get("seen_count", 0)) + 1
                distinct_users = len(users)
                await c.execute(
                    """
                    UPDATE memory_candidates
                    SET content_sample=?, last_seen=?, seen_count=?, distinct_user_count=?, last_user_id=?, last_user_name=?,
                        user_ids_json=?, channel_ids_json=?, source_types_json=?, last_reason=?
                    WHERE id=?
                    """,
                    (
                        cleaned,
                        now_ts,
                        seen_count,
                        distinct_users,
                        uid,
                        user_name,
                        self._set_json(users),
                        self._set_json(channels),
                        self._set_json(sources),
                        "observed",
                        candidate["id"],
                    ),
                )
                candidate_id = candidate["id"]
            else:
                seen_count = 1
                distinct_users = 1
                await c.execute(
                    """
                    INSERT INTO memory_candidates (
                        normalized_content, content_sample, first_seen, last_seen, seen_count, distinct_user_count,
                        last_user_id, last_user_name, user_ids_json, channel_ids_json, source_types_json, promoted, last_reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                    """,
                    (
                        normalized,
                        cleaned,
                        now_ts,
                        now_ts,
                        seen_count,
                        distinct_users,
                        uid,
                        user_name,
                        self._set_json({uid}),
                        self._set_json({cid} if cid else set()),
                        self._set_json({str(source or "unknown")}),
                        "new_candidate",
                    ),
                )
                candidate_id = c.lastrowid
            await conn.commit()

        score = self._quality_score(cleaned, seen_count, distinct_users, p)
        should_promote = force_promote or (source == "ai_tag" and p["auto_memory_direct_promote_ai_tag"]) or (
            seen_count >= int(p["auto_memory_promote_min_observations"])
            and distinct_users >= int(p["auto_memory_promote_min_distinct_users"])
            and score >= float(p["auto_memory_quality_threshold"])
        )

        if should_promote:
            memory_id = await self.add_memory(cleaned, now_ts, uid, user_name, source)
            if memory_id:
                async with self.get_conn() as conn:
                    c = await conn.cursor()
                    await c.execute(
                        "UPDATE memory_candidates SET promoted=1, promoted_memory_id=?, promoted_at=?, last_reason=? WHERE id=?",
                        (memory_id, datetime.now(timezone.utc).isoformat(), "auto_promoted", candidate_id),
                    )
                    await conn.commit()
                return {"status": "promoted", "candidate_id": candidate_id, "memory_id": memory_id, "score": score}
            existing_id = await self._find_existing_memory(normalized)
            if existing_id:
                return {"status": "duplicate_existing", "candidate_id": candidate_id, "memory_id": existing_id, "score": score}
            return {"status": "promotion_failed", "candidate_id": candidate_id, "score": score}

        return {"status": "staged", "candidate_id": candidate_id, "score": score, "seen_count": seen_count, "distinct_user_count": distinct_users}

    async def check_duplicate_memory(self, normalized: str) -> Optional[int]:
        async with self.get_conn() as conn:
            c = await conn.cursor()
            await c.execute("SELECT id FROM memory WHERE normalized_content = ? LIMIT 1", (normalized,))
            row = await c.fetchone()
            if row:
                return int(row["id"])
            await c.execute(
                "SELECT promoted_memory_id FROM memory_candidates WHERE normalized_content=? AND promoted=1 AND promoted_memory_id IS NOT NULL LIMIT 1",
                (normalized,),
            )
            row = await c.fetchone()
            if row and row["promoted_memory_id"]:
                return int(row["promoted_memory_id"])
        return None

    async def check_duplicate_world_book(self, normalized: str) -> Optional[int]:
        async with self.get_conn() as conn:
            c = await conn.cursor()
            await c.execute("SELECT id FROM world_book WHERE LOWER(content) = ? LIMIT 1", (normalized,))
            row = await c.fetchone()
            if row:
                return int(row["id"])
        return None

    async def get_all_memories(self) -> List[Dict[str, Any]]:
        async with self.get_conn() as conn:
            c = await conn.cursor()
            await c.execute("SELECT * FROM memory ORDER BY timestamp DESC")
            return [dict(r) for r in await c.fetchall()]

    async def _get_memory_embedding(self, memory_id: int) -> Optional[List[float]]:
        async with self.get_conn() as conn:
            c = await conn.cursor()
            await c.execute("SELECT embedding FROM memory WHERE id=?", (memory_id,))
            row = await c.fetchone()
            if row and row["embedding"]:
                import struct
                data = row["embedding"]
                try:
                    n = len(data) // 8
                    return list(struct.unpack(f">{n}d", data))
                except struct.error:
                    return None
        return None

    async def _set_memory_embedding(self, memory_id: int, embedding: List[float]) -> None:
        import struct
        data = struct.pack(f">{len(embedding)}d", *embedding)
        async with self.get_conn() as conn:
            c = await conn.cursor()
            await c.execute("UPDATE memory SET embedding=? WHERE id=?", (data, memory_id))
            await conn.commit()

    async def get_relevant_memories(self, query_text: str, top_k: int = 12, char_limit: int = 2200, max_age_days: int = 365, config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        top_k = max(1, min(50, int(top_k)))
        char_limit = max(300, min(20000, int(char_limit)))
        max_age_days = max(1, min(3650, int(max_age_days)))
        q_tokens = set(self._tokens(query_text, 20))
        use_embedding = bool(config.get("memory_embedding_enabled", False)) if config else False
        use_rerank = bool(config.get("memory_rerank_enabled", False)) if config else False

        rows: List[Dict[str, Any]] = []
        seen: Set[int] = set()
        async with self.get_conn() as conn:
            c = await conn.cursor()
            if q_tokens:
                def _fts5_quote(token: str) -> str:
                    safe = token.replace('"', '""')
                    return f'"{safe}"'
                match = " OR ".join(_fts5_quote(t) for t in q_tokens)
                try:
                    await c.execute(
                        """
                        SELECT m.*, COALESCE(ms.recall_count,0) AS recall_count, bm25(memory_fts) AS fts_rank
                        FROM memory m JOIN memory_fts ON memory_fts.rowid=m.id
                        LEFT JOIN memory_stats ms ON ms.memory_id=m.id
                        WHERE memory_fts MATCH ? ORDER BY fts_rank ASC LIMIT ?
                        """,
                        (match, top_k * 6),
                    )
                    for r in await c.fetchall():
                        d = dict(r)
                        rows.append(d)
                        seen.add(int(d["id"]))
                except aiosqlite.Error:
                    logger.warning("FTS5 query failed for memory recall (query tokens: %s)", list(q_tokens)[:10])
            await c.execute(
                """
                SELECT m.*, COALESCE(ms.recall_count,0) AS recall_count, 0 AS fts_rank
                FROM memory m LEFT JOIN memory_stats ms ON ms.memory_id=m.id
                ORDER BY m.timestamp DESC LIMIT ?
                """,
                (max(100, top_k * 6),),
            )
            for r in await c.fetchall():
                d = dict(r)
                mid = int(d["id"])
                if mid not in seen:
                    rows.append(d)

        # --- Embedding semantic filtering ---
        if use_embedding and rows and config:
            try:
                from .embedding_service import get_embedding, cosine_similarity
                query_emb = await get_embedding(query_text, config)

                if query_emb:
                    emb_candidates: List[Tuple[float, Dict[str, Any]]] = []
                    for row in rows:
                        mid = int(row["id"])
                        cached = await self._get_memory_embedding(mid)
                        if cached is None:
                            plain = self._strip_tag(str(row.get("content", "")))
                            if not plain:
                                continue
                            try:
                                new_emb = await get_embedding(plain, config)
                                if new_emb:
                                    await self._set_memory_embedding(mid, new_emb)
                                    cached = new_emb
                            except Exception:
                                pass
                        if cached:
                            sim = cosine_similarity(query_emb, cached)
                            emb_candidates.append((sim, row))
                    emb_candidates.sort(key=lambda x: x[0], reverse=True)
                    keep = min(top_k * 3, len(emb_candidates))
                    rows = [row for _, row in emb_candidates[:keep]]
                    seen = {int(r["id"]) for r in rows}
            except Exception:
                logger.warning("Embedding filtering failed, falling back to FTS5 results", exc_info=True)

        # --- Rerank fine-ranking ---
        if use_rerank and rows and config:
            try:
                from .rerank_service import rerank as rerank_fn
                candidates_text: List[str] = []
                candidates_map: list = []
                for row in rows:
                    plain = self._strip_tag(str(row.get("content", "")))
                    if not plain:
                        continue
                    candidates_text.append(plain)
                    candidates_map.append(row)
                if candidates_text:
                    reranked = await rerank_fn(query_text, candidates_text, config, top_n=top_k)
                    if reranked:
                        rows = []
                        for idx, _score in reranked:
                            if idx < len(candidates_map):
                                rows.append(candidates_map[idx])
            except Exception:
                logger.warning("Rerank failed, falling back to embedding/FTS5 results", exc_info=True)

        now = datetime.now(timezone.utc)
        scored: List[Tuple[float, Dict[str, Any]]] = []
        for row in rows:
            age = (now - self._dt(row.get("timestamp"))).total_seconds() / 86400.0
            if age > max_age_days:
                continue
            plain = self._strip_tag(str(row.get("content", "")))
            if not plain:
                continue
            mt = set(self._tokens(plain, 24))
            overlap = (len(q_tokens & mt) / max(1, len(q_tokens))) if q_tokens else 0.0
            recency = math.exp(-max(0.0, age) / 45.0)
            novelty = 1.0 / (1.0 + math.log1p(int(row.get("recall_count", 0))))
            fts = 1.0 / (1.0 + abs(float(row.get("fts_rank") or 0.0)))
            source_boost = 0.06 if str(row.get("source") or "") in {"conversation", "tool", "manual"} else 0.02
            score = (0.50 * overlap + 0.20 * recency + 0.15 * novelty + 0.10 * fts + source_boost) if q_tokens else (0.65 * recency + 0.25 * novelty + source_boost)
            row["_plain"] = plain
            scored.append((score, row))
        scored.sort(key=lambda x: x[0], reverse=True)
        chosen: List[Dict[str, Any]] = []
        payload: List[Tuple[int, float]] = []
        chars = 0
        for score, row in scored:
            if len(chosen) >= top_k:
                break
            plain = row.get("_plain", "")
            if chars + len(plain) + 4 > char_limit:
                continue
            chars += len(plain) + 4
            payload.append((int(row["id"]), float(score)))
            row.pop("_plain", None)
            chosen.append(row)
        await self._record_recall(payload)
        return chosen

    async def _record_recall(self, payload: List[Tuple[int, float]]) -> None:
        if not payload:
            return
        now = datetime.now(timezone.utc).isoformat()
        async with self.get_conn() as conn:
            c = await conn.cursor()
            for memory_id, score in payload:
                await c.execute(
                    """
                    INSERT INTO memory_stats (memory_id, recall_count, last_recalled_at, last_recall_score)
                    VALUES (?, 1, ?, ?)
                    ON CONFLICT(memory_id) DO UPDATE SET
                        recall_count = memory_stats.recall_count + 1,
                        last_recalled_at = excluded.last_recalled_at,
                        last_recall_score = excluded.last_recall_score
                    """,
                    (memory_id, now, score),
                )
            await conn.commit()

    async def get_memory_candidates(self, include_promoted: bool = False, limit: int = 200) -> List[Dict[str, Any]]:
        limit = max(1, min(2000, int(limit)))
        async with self.get_conn() as conn:
            c = await conn.cursor()
            if include_promoted:
                await c.execute("SELECT * FROM memory_candidates ORDER BY promoted ASC, seen_count DESC, last_seen DESC LIMIT ?", (limit,))
            else:
                await c.execute("SELECT * FROM memory_candidates WHERE promoted=0 ORDER BY seen_count DESC, last_seen DESC LIMIT ?", (limit,))
            rows = [dict(r) for r in await c.fetchall()]
        for row in rows:
            row["user_ids"] = sorted(self._set_from_json(row.get("user_ids_json")))
            row["channel_ids"] = sorted(self._set_from_json(row.get("channel_ids_json")))
            row["source_types"] = sorted(self._set_from_json(row.get("source_types_json")))
            row.pop("user_ids_json", None)
            row.pop("channel_ids_json", None)
            row.pop("source_types_json", None)
        return rows

    async def delete_memory_candidate(self, candidate_id: int) -> bool:
        async with self.get_conn() as conn:
            c = await conn.cursor()
            await c.execute("DELETE FROM memory_candidates WHERE id=?", (candidate_id,))
            await conn.commit()
            return c.rowcount > 0

    async def promote_memory_candidate(self, candidate_id: int, source: str = "manual_promote") -> Optional[int]:
        async with self.get_conn() as conn:
            c = await conn.cursor()
            await c.execute("SELECT * FROM memory_candidates WHERE id=? LIMIT 1", (candidate_id,))
            row = await c.fetchone()
            if not row:
                return None
            item = dict(row)
        if item.get("promoted") and item.get("promoted_memory_id"):
            return int(item["promoted_memory_id"])
        ts = datetime.now(timezone.utc).isoformat()
        memory_id = await self.add_memory(
            content=item.get("content_sample", ""),
            timestamp=ts,
            user_id=str(item.get("last_user_id") or "system"),
            user_name=str(item.get("last_user_name") or "system"),
            source=source,
        )
        if memory_id:
            async with self.get_conn() as conn:
                c = await conn.cursor()
                await c.execute(
                    "UPDATE memory_candidates SET promoted=1, promoted_memory_id=?, promoted_at=?, last_reason=? WHERE id=?",
                    (memory_id, ts, "manual_promoted", candidate_id),
                )
                await conn.commit()
            return memory_id
        return await self._find_existing_memory(str(item.get("normalized_content") or ""))

    async def delete_memory(self, memory_id: int) -> bool:
        async with self.get_conn() as conn:
            c = await conn.cursor()
            await c.execute("DELETE FROM memory WHERE id=?", (memory_id,))
            deleted = c.rowcount > 0
            await c.execute("DELETE FROM memory_stats WHERE memory_id=?", (memory_id,))
            await c.execute(
                "UPDATE memory_candidates SET promoted=0, promoted_memory_id=NULL, promoted_at=NULL, last_reason=? WHERE promoted_memory_id=?",
                ("promoted_memory_deleted", memory_id),
            )
            await conn.commit()
            return deleted

    async def update_memory(self, memory_id: int, new_content: str) -> bool:
        async with self.get_conn() as conn:
            c = await conn.cursor()
            await c.execute("SELECT content FROM memory WHERE id=?", (memory_id,))
            row = await c.fetchone()
            if not row:
                return False
            content = row["content"]
            if "[memory" in (content or ""):
                try:
                    tag, _ = content.split("]", 1)
                    tag += "]"
                except ValueError:
                    tag = ""
            else:
                tag = ""
            await c.execute("UPDATE memory SET content=? WHERE id=?", (f"{tag} {new_content}".strip(), memory_id))
            await conn.commit()
            return c.rowcount > 0

    # ------------------------------------------------------------------
    # World Book methods
    # ------------------------------------------------------------------

    async def add_world_book_entry(self, keywords: str, content: str, linked_user_id: Optional[str] = None, source: Optional[str] = None) -> int:
        async with self.get_conn() as conn:
            c = await conn.cursor()
            await c.execute("INSERT INTO world_book (keywords, content, linked_user_id, source) VALUES (?, ?, ?, ?)", (keywords, content, linked_user_id, source))
            await conn.commit()
            return c.lastrowid

    async def get_all_world_book_entries(self) -> List[Dict[str, Any]]:
        async with self.get_conn() as conn:
            c = await conn.cursor()
            await c.execute("SELECT * FROM world_book ORDER BY id")
            return [dict(r) for r in await c.fetchall()]

    async def update_world_book_entry(self, entry_id: int, keywords: str, content: str, enabled: bool, linked_user_id: Optional[str] = None) -> bool:
        async with self.get_conn() as conn:
            c = await conn.cursor()
            await c.execute(
                "UPDATE world_book SET keywords=?, content=?, enabled=?, linked_user_id=? WHERE id=?",
                (keywords, content, 1 if enabled else 0, linked_user_id, entry_id),
            )
            await conn.commit()
            return c.rowcount > 0

    async def delete_world_book_entry(self, entry_id: int) -> bool:
        async with self.get_conn() as conn:
            c = await conn.cursor()
            await c.execute("DELETE FROM world_book WHERE id=?", (entry_id,))
            await conn.commit()
            return c.rowcount > 0

    async def get_world_book_entries_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        async with self.get_conn() as conn:
            c = await conn.cursor()
            await c.execute("SELECT id, keywords, content FROM world_book WHERE enabled=1 AND linked_user_id=?", (user_id,))
            return [dict(r) for r in await c.fetchall()]

    async def find_world_book_entries_for_text(self, text: str) -> List[Dict[str, Any]]:
        lower = (text or "").lower()
        if not lower.strip():
            return []
        tokens = self._extract_search_tokens(lower)
        if not tokens:
            return []
        try:
            entries = await self._find_world_book_candidates_via_fts(tokens)
        except aiosqlite.Error:
            entries = await self._find_world_book_candidates_full_scan()
        return self._filter_keyword_matches(entries, lower)

    def _extract_search_tokens(self, text: str) -> List[str]:
        raw = re.findall(r"[0-9A-Za-z_\u4e00-\u9fff]+", text)
        out, seen = [], set()
        for token in raw:
            t = token.strip().lower()
            if not t or len(t) < 2 or t in seen:
                continue
            seen.add(t)
            out.append(t)
            if len(out) >= 12:
                break
        return out

    async def _find_world_book_candidates_via_fts(self, query_tokens: List[str]) -> List[Dict[str, Any]]:
        def _fts5_quote(token: str) -> str:
            safe = token.replace('"', '""')
            return f'"{safe}"'
        match_query = " OR ".join(_fts5_quote(t) for t in query_tokens)
        async with self.get_conn() as conn:
            c = await conn.cursor()
            await c.execute(
                """
                SELECT wb.id, wb.keywords, wb.content
                FROM world_book wb
                JOIN world_book_fts fts ON wb.id = fts.rowid
                WHERE wb.enabled = 1 AND world_book_fts MATCH ?
                """,
                (match_query,),
            )
            return [dict(r) for r in await c.fetchall()]

    async def _find_world_book_candidates_full_scan(self) -> List[Dict[str, Any]]:
        async with self.get_conn() as conn:
            c = await conn.cursor()
            await c.execute("SELECT id, keywords, content FROM world_book WHERE enabled = 1")
            return [dict(r) for r in await c.fetchall()]

    def _filter_keyword_matches(self, entries: List[Dict[str, Any]], lower_text: str) -> List[Dict[str, Any]]:
        matched, added = [], set()
        for entry in entries:
            keywords = [k.strip().lower() for k in entry.get("keywords", "").split(",") if k.strip()]
            for keyword in keywords:
                if keyword in lower_text:
                    if entry["id"] not in added:
                        matched.append(entry)
                        added.add(entry["id"])
                    break
        return matched


_knowledge_manager: Optional[KnowledgeManager] = None


def get_knowledge_manager(bot_id: str = None) -> KnowledgeManager:
    global _knowledge_manager
    try:
        from .. import state
        mgr = state.bot_manager
        if bot_id and mgr:
            inst = mgr.get(bot_id)
            if inst and inst._knowledge_manager:
                return inst._knowledge_manager
        if mgr and mgr._instances:
            first = next(iter(mgr._instances.values()))
            if first._knowledge_manager:
                return first._knowledge_manager
    except Exception:
        pass
    if _knowledge_manager is None:
        _knowledge_manager = KnowledgeManager()
    return _knowledge_manager


# Lazy import for logger to avoid circular dependency at module level
import logging
logger = logging.getLogger(__name__)
