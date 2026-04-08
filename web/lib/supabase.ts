import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!

export const supabase = createClient(supabaseUrl, supabaseKey)

export type Item = {
  id: string
  type: 'book' | 'film' | 'show' | 'other'
  title: string
  creator: string | null
  year: number | null
  cover_url: string | null
  description: string | null
  genres: string[] | null
  status: 'want' | 'in_progress' | 'done' | 'abandoned'
  feeling: 'essential' | 'loved' | 'average' | 'not_for_me' | 'regret' | null
  vibe_tags: string[] | null
  would_revisit: 'yes' | 'maybe' | 'no' | null
  highlight_quote: string | null
  summary: string | null
  telegram_id: number | null
  started_at: string | null
  finished_at: string | null
  added_at: string
}
