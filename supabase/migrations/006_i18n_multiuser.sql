-- ============================================================
-- Migration 006 — i18n + named user profiles
-- Adds users table for profile switcher, dual-language columns
-- on items, and telegram_id on recommendations
-- ============================================================

-- Named user profiles (linked to telegram accounts)
CREATE TABLE IF NOT EXISTS users (
  id            uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  telegram_id   BIGINT UNIQUE,
  name          text NOT NULL,
  lang          text NOT NULL DEFAULT 'en' CHECK (lang IN ('en', 'ru')),
  avatar_emoji  text NOT NULL DEFAULT '🎬',
  color         text NOT NULL DEFAULT '#6366f1',
  created_at    timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS users_telegram_id_idx ON users(telegram_id);

-- Dual-language content columns on items
ALTER TABLE items
  ADD COLUMN IF NOT EXISTS title_ru        text,
  ADD COLUMN IF NOT EXISTS description_ru  text,
  ADD COLUMN IF NOT EXISTS highlights_ru   text[],
  ADD COLUMN IF NOT EXISTS summary_ru      text,
  ADD COLUMN IF NOT EXISTS vibe_tags_ru    text[];

-- Add telegram_id to recommendations so each user gets their own
ALTER TABLE recommendations
  ADD COLUMN IF NOT EXISTS telegram_id BIGINT;

CREATE INDEX IF NOT EXISTS recommendations_telegram_id_idx ON recommendations(telegram_id);
