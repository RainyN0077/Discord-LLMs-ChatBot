-- 数据库初始化脚本
-- 创建应用所需的所有表和触发器

-- 1. 创建 world_book 表
CREATE TABLE IF NOT EXISTS world_book (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keywords TEXT NOT NULL,
    content TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    linked_user_id TEXT
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

-- 3. 创建 FTS 虚拟表和触发器
CREATE VIRTUAL TABLE IF NOT EXISTS world_book_fts
USING fts5(keywords, content, content='world_book', content_rowid='id');

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