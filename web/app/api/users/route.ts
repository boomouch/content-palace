import { NextResponse } from 'next/server'
import { createServerClient } from '@/lib/supabase-server'

export async function GET() {
  const db = createServerClient()
  const { data } = await db
    .from('users')
    .select('id, name, telegram_id, lang, avatar_emoji, color')
    .order('created_at', { ascending: true })
  return NextResponse.json(data || [])
}
