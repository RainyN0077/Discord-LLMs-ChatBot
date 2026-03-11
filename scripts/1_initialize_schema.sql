-- 数据库初始化脚本
-- 创建应用所需的所有表和触发器

-- 1. 创建 world_book 表
CREATE TABLE IF NOT EXISTS world_book (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keywords TEXT NOT NULL,
    content TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    linked_user_id TEXT,
    source TEXT
);

-- 2. 创建 memory 表
CREATE TABLE IF NOT EXISTS memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL UNIQUE,
    timestamp TEXT NOT NULL,
    user_id TEXT,
    user_name TEXT,
    source TEXT
);

-- 2.1 创建 memory_candidates 表（自动记忆候选池）
CREATE TABLE IF NOT EXISTS memory_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    normalized_content TEXT NOT NULL UNIQUE,
    content_sample TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    seen_count INTEGER NOT NULL DEFAULT 1,
    distinct_user_count INTEGER NOT NULL DEFAULT 1,
    last_user_id TEXT,
    last_user_name TEXT,
    user_ids_json TEXT NOT NULL DEFAULT '[]',
    channel_ids_json TEXT NOT NULL DEFAULT '[]',
    source_types_json TEXT NOT NULL DEFAULT '[]',
    promoted INTEGER NOT NULL DEFAULT 0,
    promoted_memory_id INTEGER,
    promoted_at TEXT,
    last_reason TEXT,
    FOREIGN KEY(promoted_memory_id) REFERENCES memory(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_memory_candidates_promoted_last_seen
ON memory_candidates(promoted, last_seen DESC);

CREATE INDEX IF NOT EXISTS idx_memory_candidates_seen_count
ON memory_candidates(seen_count DESC);

-- 2.2 创建 memory_stats 表（记忆召回统计）
CREATE TABLE IF NOT EXISTS memory_stats (
    memory_id INTEGER PRIMARY KEY,
    recall_count INTEGER NOT NULL DEFAULT 0,
    last_recalled_at TEXT,
    last_recall_score REAL NOT NULL DEFAULT 0,
    FOREIGN KEY(memory_id) REFERENCES memory(id) ON DELETE CASCADE
);

-- 3. 创建 FTS 虚拟表和触发器
CREATE VIRTUAL TABLE IF NOT EXISTS world_book_fts
USING fts5(keywords, content, content='world_book', content_rowid='id');

CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts
USING fts5(content, content='memory', content_rowid='id');

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

CREATE TRIGGER IF NOT EXISTS memory_after_insert
AFTER INSERT ON memory
BEGIN
    INSERT INTO memory_fts(rowid, content)
    VALUES (new.id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS memory_after_delete
AFTER DELETE ON memory
BEGIN
    INSERT INTO memory_fts(memory_fts, rowid, content)
    VALUES ('delete', old.id, old.content);
END;

CREATE TRIGGER IF NOT EXISTS memory_after_update
AFTER UPDATE ON memory
BEGIN
    INSERT INTO memory_fts(memory_fts, rowid, content)
    VALUES ('delete', old.id, old.content);
    INSERT INTO memory_fts(rowid, content)
    VALUES (new.id, new.content);
END;

-- 重建 FTS 索引，确保老数据可检索
INSERT INTO world_book_fts(world_book_fts) VALUES ('rebuild');
INSERT INTO memory_fts(memory_fts) VALUES ('rebuild');
