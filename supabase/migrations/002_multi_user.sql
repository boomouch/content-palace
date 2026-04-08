-- ============================================================
-- Migration 002 — Multi-user support
-- Add telegram_id to items and suggestions so each user's
-- library is completely separate
-- ============================================================

ALTER TABLE items ADD COLUMN telegram_id BIGINT;
ALTER TABLE suggestions ADD COLUMN telegram_id BIGINT;

CREATE INDEX idx_items_telegram_id ON items(telegram_id);
CREATE INDEX idx_suggestions_telegram_id ON suggestions(telegram_id);

-- Update the library and want_list views to require telegram_id
DROP VIEW IF EXISTS library;
DROP VIEW IF EXISTS want_list;

CREATE VIEW library AS
  SELECT * FROM items
  WHERE status IN ('done', 'in_progress', 'abandoned')
  ORDER BY
    CASE WHEN status = 'in_progress' THEN 0 ELSE 1 END,
    finished_at DESC NULLS LAST,
    added_at DESC;

CREATE VIEW want_list AS
  SELECT * FROM items
  WHERE status = 'want'
  ORDER BY added_at DESC;
