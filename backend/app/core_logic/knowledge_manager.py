import sqlite3
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

class KnowledgeManager:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            # 在Docker容器中，工作目录是 /app，数据卷挂载到了 /app/data
            # 因此我们直接使用相对路径或绝对路径 /app/data
            db_dir = 'data'
            os.makedirs(db_dir, exist_ok=True)
            self.db_path = os.path.join(db_dir, 'knowledge_base.sqlite')
        else:
            self.db_path = db_path
        
        self.init_db()

    def get_conn(self):
        # 增加超时参数（单位：秒）。当数据库被锁定时，
        # 连接会等待指定的时间，而不是立即失败。
        # 15秒对于web请求来说是一个比较长的等待时间，但可以显著减少锁冲突。
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_conn() as conn:
            cursor = conn.cursor()
            # Create memory table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL UNIQUE,
                timestamp TEXT NOT NULL,
                user_id TEXT,
                user_name TEXT,
                source TEXT
            )
            """)
            # Create world_book table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS world_book (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keywords TEXT NOT NULL,
                content TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1
            )
            """)
            # Create FTS5 virtual table for world_book
            cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS world_book_fts
            USING fts5(keywords, content, content='world_book', content_rowid='id')
            """)
            # Create triggers to keep FTS table in sync with world_book table
            cursor.executescript("""
            CREATE TRIGGER IF NOT EXISTS world_book_after_insert
            AFTER INSERT ON world_book
            BEGIN
                INSERT INTO world_book_fts(rowid, keywords, content)
                VALUES (new.id, new.keywords, new.content);
            END;

            CREATE TRIGGER IF NOT EXISTS world_book_after_delete
            AFTER DELETE ON world_book
            BEGIN
                INSERT INTO world_book_fts(world_book_fts, rowid, keywords, content)
                VALUES ('delete', old.id, old.keywords, old.content);
            END;

            CREATE TRIGGER IF NOT EXISTS world_book_after_update
            AFTER UPDATE ON world_book
            BEGIN
                INSERT INTO world_book_fts(world_book_fts, rowid, keywords, content)
                VALUES ('delete', old.id, old.keywords, old.content);
                INSERT INTO world_book_fts(rowid, keywords, content)
                VALUES (new.id, new.keywords, new.content);
            END;
            """)
            conn.commit()

    # Memory methods
    def add_memory(self, content: str, timestamp: str, user_id: str, user_name: str, source: str) -> Optional[int]:
        """
        Adds a new piece of information to the long-term memory.
        The content is prefixed with a machine-readable structured tag.
        """
        try:
            # Escape potential quotes in user_name to avoid breaking the tag format
            safe_user_name = user_name.replace('"', '""')

            # Construct the structured, machine-readable tag
            structured_tag = (
                f'[memory timestamp="{timestamp}" '
                f'source="{source}" '
                f'user_name="{safe_user_name}" '
                f'user_id="{user_id}"]'
            )

            # Prepend the tag to the original content
            tagged_content = f"{structured_tag} {content}"

            with self.get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO memory (content, timestamp, user_id, user_name, source) VALUES (?, ?, ?, ?, ?)",
                    (tagged_content, timestamp, user_id, user_name, source)
                )
                conn.commit()
                return cursor.lastrowid
        except sqlite3.IntegrityError:
            # This happens if the tagged_content is not unique.
            return None

    def get_all_memories(self) -> List[Dict[str, Any]]:
        with self.get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM memory ORDER BY timestamp DESC")
            return [dict(row) for row in cursor.fetchall()]

    def delete_memory(self, memory_id: int) -> bool:
        with self.get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM memory WHERE id = ?", (memory_id,))
            conn.commit()
            return cursor.rowcount > 0

    # World Book methods
    def add_world_book_entry(self, keywords: str, content: str) -> int:
        with self.get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO world_book (keywords, content) VALUES (?, ?)", (keywords, content))
            conn.commit()
            return cursor.lastrowid

    def get_all_world_book_entries(self) -> List[Dict[str, Any]]:
        with self.get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM world_book ORDER BY id")
            return [dict(row) for row in cursor.fetchall()]

    def update_world_book_entry(self, entry_id: int, keywords: str, content: str, enabled: bool) -> bool:
        with self.get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE world_book
            SET keywords = ?, content = ?, enabled = ?
            WHERE id = ?
            """, (keywords, content, 1 if enabled else 0, entry_id))
            conn.commit()
            return cursor.rowcount > 0

    def delete_world_book_entry(self, entry_id: int) -> bool:
        with self.get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM world_book WHERE id = ?", (entry_id,))
            conn.commit()
            return cursor.rowcount > 0

    def find_world_book_entries_for_text(self, text: str) -> List[Dict[str, Any]]:
        with self.get_conn() as conn:
            cursor = conn.cursor()
            # Sanitize the search query for FTS5
            # This creates a search query where each word in the input text must be present.
            query = ' AND '.join(text.split())
            
            cursor.execute("""
                SELECT wb.keywords, wb.content
                FROM world_book wb
                JOIN world_book_fts fts ON wb.id = fts.rowid
                WHERE fts.keywords MATCH ? AND wb.enabled = 1
            """, (query,))
            
            return [dict(row) for row in cursor.fetchall()]

# Singleton instance
knowledge_manager = KnowledgeManager()