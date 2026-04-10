import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!

export const supabase = createClient(supabaseUrl, supabaseKey)

export type Recommendation = {
  id: string
  title: string
  title_ru: string | null
  type: 'film' | 'show' | 'book'
  creator: string | null
  year: number | null
  cover_url: string | null
  description: string | null
  genres: string[] | null
  why: string
  why_ru: string | null
  filters: Record<string, unknown>
  dismissed: boolean
  dismiss_reason: string | null
  added_to_want: boolean
  created_at: string
}

export type Item = {
  id: string
  type: 'book' | 'film' | 'show' | 'other'
  subtype: string | null
  title: string
  title_ru: string | null
  creator: string | null
  year: number | null
  cover_url: string | null
  description: string | null
  description_ru: string | null
  genres: string[] | null
  genres_ru: string[] | null
  status: 'want' | 'in_progress' | 'done' | 'abandoned'
  feeling: 'essential' | 'loved' | 'average' | 'not_for_me' | 'regret' | null
  vibe_tags: string[] | null
  vibe_tags_ru: string[] | null
  highlights_ru: string[] | null
  summary_ru: string | null
  would_revisit: 'yes' | 'maybe' | 'no' | null
  highlight_quote: string | null
  summary: string | null
  telegram_id: number | null
  started_at: string | null
  finished_at: string | null
  added_at: string
}

export type User = {
  id: string
  telegram_id: number
  name: string
  lang: 'en' | 'ru'
  avatar_emoji: string
  color: string
}
