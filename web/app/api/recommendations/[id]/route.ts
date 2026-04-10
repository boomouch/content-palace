import { NextRequest, NextResponse } from 'next/server'
import { createServerClient } from '@/lib/supabase-server'

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  const { action, reason, item } = await req.json()
  const db = createServerClient()

  if (action === 'dismiss') {
    await db
      .from('recommendations')
      .update({ dismissed: true, dismiss_reason: reason || null })
      .eq('id', id)
    return NextResponse.json({ ok: true })
  }

  if (action === 'want') {
    await db.from('items').insert({
      title: item.title,
      type: item.type,
      creator: item.creator || null,
      year: item.year || null,
      cover_url: item.cover_url || null,
      description: item.description || null,
      genres: item.genres || null,
      status: 'want',
    })
    await db
      .from('recommendations')
      .update({ added_to_want: true })
      .eq('id', id)
    return NextResponse.json({ ok: true })
  }

  return NextResponse.json({ error: 'Unknown action' }, { status: 400 })
}
