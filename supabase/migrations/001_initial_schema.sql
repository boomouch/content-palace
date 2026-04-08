-- ============================================================
-- Content Palace — Initial Schema
-- ============================================================

-- Enable useful extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- fuzzy search for deduplication

-- ============================================================
-- ITEMS — the core table, one row per book/film/show/other
-- ============================================================
CREATE TABLE items (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  -- Content info
  type            TEXT NOT NULL CHECK (type IN ('book', 'film', 'show', 'other')),
  title           TEXT NOT NULL,
  creator         TEXT,           -- author / director / show creator
  year            INTEGER,
  cover_url       TEXT,           -- stored in Supabase Storage
  description     TEXT,
  genres          TEXT[],         -- e.g. ['drama', 'thriller']
  source_url      TEXT,           -- for other content (articles, youtube, etc.)

  -- External metadata
  external_id     TEXT,           -- TMDB id, Open Library key, etc.
  external_source TEXT,           -- 'tmdb' | 'openlibrary' | 'scraped'
  metadata_raw    JSONB,          -- full raw API response, never discard
  metadata_fetched_at TIMESTAMPTZ,

  -- User's relationship with this item
  status          TEXT NOT NULL DEFAULT 'want'
                  CHECK (status IN ('want', 'in_progress', 'done', 'abandoned')),
  started_at      DATE,
  finished_at     DATE,

  -- User's reflection (populated after finishing)
  feeling         TEXT CHECK (feeling IN (
                    'essential', 'loved', 'good', 'fine', 'not_for_me', 'regret'
                  )),
  vibe_tags       TEXT[],         -- AI-generated from user's words e.g. ['slow burn', 'dark']
  would_revisit   TEXT CHECK (would_revisit IN ('yes', 'maybe', 'no')),
  highlight_quote TEXT,           -- a quote that stuck with them
  summary         TEXT,           -- AI-structured summary of their thoughts

  -- Raw input preserved forever
  raw_messages    TEXT[],         -- every Telegram message the user sent about this item

  -- Visibility
  is_public       BOOLEAN DEFAULT false,

  -- Timestamps
  added_at        TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- AI SUGGESTIONS — things Claude recommended to the user
-- ============================================================
CREATE TABLE suggestions (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  source_item_id  UUID REFERENCES items(id) ON DELETE CASCADE,

  suggested_title TEXT NOT NULL,
  suggested_type  TEXT NOT NULL CHECK (suggested_type IN ('book', 'film', 'show', 'other')),
  reason          TEXT,           -- why Claude suggested it

  status          TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'added', 'dismissed')),

  created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TELEGRAM SESSIONS — tracks bot state per conversation
-- ============================================================
CREATE TABLE telegram_sessions (
  telegram_id     BIGINT PRIMARY KEY,
  telegram_handle TEXT,

  -- Conversation state machine
  state           TEXT NOT NULL DEFAULT 'idle'
                  CHECK (state IN (
                    'idle',
                    'reflecting',         -- mid-reflection conversation after finishing
                    'awaiting_feeling',   -- waiting for feeling selection
                    'awaiting_revisit',   -- waiting for would_revisit answer
                    'awaiting_quote'      -- waiting for optional quote
                  )),
  state_item_id   UUID REFERENCES items(id) ON DELETE SET NULL,
  state_payload   JSONB,          -- extra context for current state

  last_active_at  TIMESTAMPTZ DEFAULT NOW(),
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- INDEXES — for fast filtering and searching
-- ============================================================

-- Filter by status (most common query: "show me done items")
CREATE INDEX idx_items_status    ON items(status);
CREATE INDEX idx_items_type      ON items(type);
CREATE INDEX idx_items_finished  ON items(finished_at DESC) WHERE finished_at IS NOT NULL;
CREATE INDEX idx_items_added     ON items(added_at DESC);

-- Fuzzy title search for deduplication (powered by pg_trgm)
CREATE INDEX idx_items_title_trgm ON items USING GIN (title gin_trgm_ops);

-- Array search on genres and tags
CREATE INDEX idx_items_genres    ON items USING GIN (genres);
CREATE INDEX idx_items_vibe_tags ON items USING GIN (vibe_tags);

-- ============================================================
-- AUTO-UPDATE updated_at
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER items_updated_at
  BEFORE UPDATE ON items
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- USEFUL VIEWS
-- ============================================================

-- Items ready to display on the website (done or in_progress)
CREATE VIEW library AS
  SELECT * FROM items
  WHERE status IN ('done', 'in_progress', 'abandoned')
  ORDER BY
    CASE WHEN status = 'in_progress' THEN 0 ELSE 1 END,
    finished_at DESC NULLS LAST,
    added_at DESC;

-- Want list
CREATE VIEW want_list AS
  SELECT * FROM items
  WHERE status = 'want'
  ORDER BY added_at DESC;
