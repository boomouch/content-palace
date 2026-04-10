CREATE TABLE IF NOT EXISTS recommendations (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  title text NOT NULL,
  type text NOT NULL CHECK (type IN ('film', 'show', 'book')),
  creator text,
  year int,
  cover_url text,
  description text,
  genres text[],
  why text NOT NULL,
  filters jsonb DEFAULT '{}',
  dismissed boolean DEFAULT false,
  dismiss_reason text,
  added_to_want boolean DEFAULT false,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS recommendations_dismissed_idx ON recommendations(dismissed);
CREATE INDEX IF NOT EXISTS recommendations_created_at_idx ON recommendations(created_at DESC);
