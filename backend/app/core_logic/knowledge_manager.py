import json
import math
import os
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple


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

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_dir = "data"
            os.makedirs(db_dir, exist_ok=True)
            self.db_path = os.path.join(db_dir, "knowledge_base.sqlite")
        else:
            self.db_path = db_path
        self.init_db()

    def get_conn(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        scripts_dir = "/app/scripts"
        if not os.path.isdir(scripts_dir):
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            scripts_dir = os.path.join(base_dir, "scripts")
        init_script_path = os.path.join(scripts_dir, "1_initialize_schema.sql")
        if not os.path.exists(init_script_path):
            print(f"CRITICAL: Database initialization script not found at {init_script_path}")
            return
        with self.get_conn() as conn:
            cursor = conn.cursor()
            try:
                with open(init_script_path, "r", encoding="utf-8") as f:
                    cursor.executescript(f.read())
                self._ensure_runtime_schema(cursor)
                conn.commit()
            except sqlite3.Error:
                conn.rollback()
                raise

    def _ensure_runtime_schema(self, cursor: sqlite3.Cursor) -> None:
        cursor.execute("PRAGMA table_info(memory_candidates)")
        cols = {row[1] for row in cursor.fetchall()}
        if cols:
            if "last_user_id" not in cols:
                cursor.execute("ALTER TABLE memory_candidates ADD COLUMN last_user_id TEXT")
            if "last_user_name" not in cols:
                cursor.execute("ALTER TABLE memory_candidates ADD COLUMN last_user_name TEXT")

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

    def _find_existing_memory(self, normalized: str) -> Optional[int]:
        with self.get_conn() as conn:
            c = conn.cursor()
            c.execute(
                "SELECT promoted_memory_id FROM memory_candidates WHERE normalized_content=? AND promoted=1 AND promoted_memory_id IS NOT NULL LIMIT 1",
                (normalized,),
            )
            row = c.fetchone()
            if row and row["promoted_memory_id"]:
                return int(row["promoted_memory_id"])
            c.execute("SELECT id, content FROM memory")
            for r in c.fetchall():
                if self._normalize(r["content"]) == normalized:
                    return int(r["id"])
        return None

    # Memory CRUD
    def add_memory(self, content: str, timestamp: str, user_id: str, user_name: str, source: str) -> Optional[int]:
        try:
            safe_user = (user_name or "Unknown").replace('"', '""')
            tag = f'[memory timestamp="{timestamp}" source="{source}" user_name="{safe_user}" user_id="{user_id}"]'
            tagged_content = f"{tag} {content}".strip()
            normalized = self._normalize(content)
            with self.get_conn() as conn:
                c = conn.cursor()
                c.execute(
                    "INSERT INTO memory (content, timestamp, user_id, user_name, source) VALUES (?, ?, ?, ?, ?)",
                    (tagged_content, timestamp, user_id, user_name, source),
                )
                memory_id = c.lastrowid
                c.execute(
                    "INSERT INTO memory_stats (memory_id, recall_count, last_recalled_at, last_recall_score) VALUES (?, 0, NULL, 0) ON CONFLICT(memory_id) DO NOTHING",
                    (memory_id,),
                )
                if normalized:
                    c.execute(
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
                conn.commit()
                return memory_id
        except sqlite3.IntegrityError:
            return None

    def ingest_memory_candidate(
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
        existing_id = self._find_existing_memory(normalized)
        if existing_id:
            return {"status": "duplicate_existing", "memory_id": existing_id}

        now = self._dt(timestamp)
        now_ts = now.isoformat()
        uid = str(user_id or "unknown_user")
        cid = str(channel_id) if channel_id is not None else ""

        with self.get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM memory_candidates WHERE normalized_content=? LIMIT 1", (normalized,))
            row = c.fetchone()
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
                c.execute(
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
                c.execute(
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
            conn.commit()

        score = self._quality_score(cleaned, seen_count, distinct_users, p)
        should_promote = force_promote or (source == "ai_tag" and p["auto_memory_direct_promote_ai_tag"]) or (
            seen_count >= int(p["auto_memory_promote_min_observations"])
            and distinct_users >= int(p["auto_memory_promote_min_distinct_users"])
            and score >= float(p["auto_memory_quality_threshold"])
        )

        if should_promote:
            memory_id = self.add_memory(cleaned, now_ts, uid, user_name, source)
            if memory_id:
                with self.get_conn() as conn:
                    c = conn.cursor()
                    c.execute(
                        "UPDATE memory_candidates SET promoted=1, promoted_memory_id=?, promoted_at=?, last_reason=? WHERE id=?",
                        (memory_id, datetime.now(timezone.utc).isoformat(), "auto_promoted", candidate_id),
                    )
                    conn.commit()
                return {"status": "promoted", "candidate_id": candidate_id, "memory_id": memory_id, "score": score}
            existing_id = self._find_existing_memory(normalized)
            if existing_id:
                return {"status": "duplicate_existing", "candidate_id": candidate_id, "memory_id": existing_id, "score": score}
            return {"status": "promotion_failed", "candidate_id": candidate_id, "score": score}

        return {"status": "staged", "candidate_id": candidate_id, "score": score, "seen_count": seen_count, "distinct_user_count": distinct_users}

    def get_all_memories(self) -> List[Dict[str, Any]]:
        with self.get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM memory ORDER BY timestamp DESC")
            return [dict(r) for r in c.fetchall()]

    def get_relevant_memories(self, query_text: str, top_k: int = 12, char_limit: int = 2200, max_age_days: int = 365) -> List[Dict[str, Any]]:
        top_k = max(1, min(50, int(top_k)))
        char_limit = max(300, min(20000, int(char_limit)))
        max_age_days = max(1, min(3650, int(max_age_days)))
        q_tokens = set(self._tokens(query_text, 20))
        rows: List[Dict[str, Any]] = []
        seen: Set[int] = set()
        with self.get_conn() as conn:
            c = conn.cursor()
            if q_tokens:
                match = " OR ".join(f'"{t}"' for t in q_tokens)
                try:
                    c.execute(
                        """
                        SELECT m.*, COALESCE(ms.recall_count,0) AS recall_count, bm25(memory_fts) AS fts_rank
                        FROM memory m JOIN memory_fts ON memory_fts.rowid=m.id
                        LEFT JOIN memory_stats ms ON ms.memory_id=m.id
                        WHERE memory_fts MATCH ? ORDER BY fts_rank ASC LIMIT ?
                        """,
                        (match, top_k * 6),
                    )
                    for r in c.fetchall():
                        d = dict(r)
                        rows.append(d)
                        seen.add(int(d["id"]))
                except sqlite3.Error:
                    pass
            c.execute(
                """
                SELECT m.*, COALESCE(ms.recall_count,0) AS recall_count, 0 AS fts_rank
                FROM memory m LEFT JOIN memory_stats ms ON ms.memory_id=m.id
                ORDER BY m.timestamp DESC LIMIT ?
                """,
                (max(100, top_k * 6),),
            )
            for r in c.fetchall():
                d = dict(r)
                mid = int(d["id"])
                if mid not in seen:
                    rows.append(d)
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
        self._record_recall(payload)
        return chosen

    def _record_recall(self, payload: List[Tuple[int, float]]) -> None:
        if not payload:
            return
        now = datetime.now(timezone.utc).isoformat()
        with self.get_conn() as conn:
            c = conn.cursor()
            for memory_id, score in payload:
                c.execute(
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
            conn.commit()

    def get_memory_candidates(self, include_promoted: bool = False, limit: int = 200) -> List[Dict[str, Any]]:
        limit = max(1, min(2000, int(limit)))
        with self.get_conn() as conn:
            c = conn.cursor()
            if include_promoted:
                c.execute("SELECT * FROM memory_candidates ORDER BY promoted ASC, seen_count DESC, last_seen DESC LIMIT ?", (limit,))
            else:
                c.execute("SELECT * FROM memory_candidates WHERE promoted=0 ORDER BY seen_count DESC, last_seen DESC LIMIT ?", (limit,))
            rows = [dict(r) for r in c.fetchall()]
        for row in rows:
            row["user_ids"] = sorted(self._set_from_json(row.get("user_ids_json")))
            row["channel_ids"] = sorted(self._set_from_json(row.get("channel_ids_json")))
            row["source_types"] = sorted(self._set_from_json(row.get("source_types_json")))
            row.pop("user_ids_json", None)
            row.pop("channel_ids_json", None)
            row.pop("source_types_json", None)
        return rows

    def delete_memory_candidate(self, candidate_id: int) -> bool:
        with self.get_conn() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM memory_candidates WHERE id=?", (candidate_id,))
            conn.commit()
            return c.rowcount > 0

    def promote_memory_candidate(self, candidate_id: int, source: str = "manual_promote") -> Optional[int]:
        with self.get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM memory_candidates WHERE id=? LIMIT 1", (candidate_id,))
            row = c.fetchone()
            if not row:
                return None
            item = dict(row)
        if item.get("promoted") and item.get("promoted_memory_id"):
            return int(item["promoted_memory_id"])
        ts = datetime.now(timezone.utc).isoformat()
        memory_id = self.add_memory(
            content=item.get("content_sample", ""),
            timestamp=ts,
            user_id=str(item.get("last_user_id") or "system"),
            user_name=str(item.get("last_user_name") or "system"),
            source=source,
        )
        if memory_id:
            with self.get_conn() as conn:
                c = conn.cursor()
                c.execute(
                    "UPDATE memory_candidates SET promoted=1, promoted_memory_id=?, promoted_at=?, last_reason=? WHERE id=?",
                    (memory_id, ts, "manual_promoted", candidate_id),
                )
                conn.commit()
            return memory_id
        return self._find_existing_memory(str(item.get("normalized_content") or ""))

    def delete_memory(self, memory_id: int) -> bool:
        with self.get_conn() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM memory WHERE id=?", (memory_id,))
            deleted = c.rowcount > 0
            c.execute("DELETE FROM memory_stats WHERE memory_id=?", (memory_id,))
            c.execute(
                "UPDATE memory_candidates SET promoted=0, promoted_memory_id=NULL, promoted_at=NULL, last_reason=? WHERE promoted_memory_id=?",
                ("promoted_memory_deleted", memory_id),
            )
            conn.commit()
            return deleted

    def update_memory(self, memory_id: int, new_content: str) -> bool:
        with self.get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT content FROM memory WHERE id=?", (memory_id,))
            row = c.fetchone()
            if not row:
                return False
            content = row["content"]
            try:
                tag, _ = content.split("]", 1)
                tag += "]"
            except ValueError:
                return False
            c.execute("UPDATE memory SET content=? WHERE id=?", (f"{tag} {new_content}".strip(), memory_id))
            conn.commit()
            return c.rowcount > 0

    # World Book methods
    def add_world_book_entry(self, keywords: str, content: str, linked_user_id: Optional[str] = None, source: Optional[str] = None) -> int:
        with self.get_conn() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO world_book (keywords, content, linked_user_id, source) VALUES (?, ?, ?, ?)", (keywords, content, linked_user_id, source))
            conn.commit()
            return c.lastrowid

    def get_all_world_book_entries(self) -> List[Dict[str, Any]]:
        with self.get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM world_book ORDER BY id")
            return [dict(r) for r in c.fetchall()]

    def update_world_book_entry(self, entry_id: int, keywords: str, content: str, enabled: bool, linked_user_id: Optional[str] = None) -> bool:
        with self.get_conn() as conn:
            c = conn.cursor()
            c.execute(
                "UPDATE world_book SET keywords=?, content=?, enabled=?, linked_user_id=? WHERE id=?",
                (keywords, content, 1 if enabled else 0, linked_user_id, entry_id),
            )
            conn.commit()
            return c.rowcount > 0

    def delete_world_book_entry(self, entry_id: int) -> bool:
        with self.get_conn() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM world_book WHERE id=?", (entry_id,))
            conn.commit()
            return c.rowcount > 0

    def get_world_book_entries_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        with self.get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT id, keywords, content FROM world_book WHERE enabled=1 AND linked_user_id=?", (user_id,))
            return [dict(r) for r in c.fetchall()]

    def find_world_book_entries_for_text(self, text: str) -> List[Dict[str, Any]]:
        lower = (text or "").lower()
        if not lower.strip():
            return []
        tokens = self._extract_search_tokens(lower)
        if not tokens:
            return []
        try:
            entries = self._find_world_book_candidates_via_fts(tokens)
        except sqlite3.Error:
            entries = self._find_world_book_candidates_full_scan()
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

    def _find_world_book_candidates_via_fts(self, query_tokens: List[str]) -> List[Dict[str, Any]]:
        match_query = " OR ".join(f'"{t}"' for t in query_tokens)
        with self.get_conn() as conn:
            c = conn.cursor()
            c.execute(
                """
                SELECT wb.id, wb.keywords, wb.content
                FROM world_book wb
                JOIN world_book_fts fts ON wb.id = fts.rowid
                WHERE wb.enabled = 1 AND world_book_fts MATCH ?
                """,
                (match_query,),
            )
            return [dict(r) for r in c.fetchall()]

    def _find_world_book_candidates_full_scan(self) -> List[Dict[str, Any]]:
        with self.get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT id, keywords, content FROM world_book WHERE enabled = 1")
            return [dict(r) for r in c.fetchall()]

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


knowledge_manager = KnowledgeManager()
