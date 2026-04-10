import Anthropic from '@anthropic-ai/sdk'
import { NextRequest, NextResponse } from 'next/server'
import { createServerClient } from '@/lib/supabase-server'

const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY })
const TMDB_KEY = process.env.TMDB_API_KEY

async function enrichWithTMDB(
  title: string,
  type: 'film' | 'show'
): Promise<{ cover_url?: string; description?: string; genres?: string[]; year?: number; creator?: string; title_ru?: string }> {
  if (!TMDB_KEY) return {}
  try {
    const endpoint = type === 'film' ? 'movie' : 'tv'
    const titleKey = type === 'film' ? 'title' : 'name'
    const searchRes = await fetch(
      `https://api.themoviedb.org/3/search/${endpoint}?api_key=${TMDB_KEY}&query=${encodeURIComponent(title)}&page=1`
    )
    const searchData = await searchRes.json()
    const result = searchData.results?.[0]
    if (!result) return {}

    const [detailRes, ruRes] = await Promise.all([
      fetch(`https://api.themoviedb.org/3/${endpoint}/${result.id}?api_key=${TMDB_KEY}&append_to_response=credits`),
      fetch(`https://api.themoviedb.org/3/${endpoint}/${result.id}?api_key=${TMDB_KEY}&language=ru-RU`),
    ])
    const detail = await detailRes.json()
    const ruDetail = await ruRes.json()

    const cover_url = detail.poster_path
      ? `https://image.tmdb.org/t/p/w500${detail.poster_path}`
      : undefined
    const description = detail.overview || undefined
    const genres: string[] = detail.genres?.map((g: { name: string }) => g.name.toLowerCase()) ?? []
    const yearStr: string | undefined = type === 'film' ? detail.release_date : detail.first_air_date
    const year = yearStr ? parseInt(yearStr.split('-')[0]) : undefined
    const creator =
      type === 'film'
        ? detail.credits?.crew?.find((c: { job: string; name: string }) => c.job === 'Director')?.name
        : detail.created_by?.[0]?.name
    const ruTitle: string | undefined = ruDetail[titleKey] || undefined
    const title_ru = ruTitle && ruTitle !== detail[titleKey] ? ruTitle : undefined

    return { cover_url, description, genres, year, creator, title_ru }
  } catch {
    return {}
  }
}

type TMDBCandidate = { title: string; type: 'film' | 'show'; year: number | null; overview: string }

async function fetchRecentFromTMDB(typeFilter: string | null): Promise<TMDBCandidate[]> {
  if (!TMDB_KEY) return []
  const types: Array<'film' | 'show'> = typeFilter === 'film' ? ['film']
    : typeFilter === 'show' ? ['show']
    : ['film', 'show']

  const results: TMDBCandidate[] = []

  for (const t of types) {
    const endpoint = t === 'film' ? 'movie' : 'tv'
    const dateParam = t === 'film' ? 'primary_release_date.gte' : 'first_air_date.gte'
    const titleKey = t === 'film' ? 'title' : 'name'
    const dateKey = t === 'film' ? 'release_date' : 'first_air_date'

    try {
      // Fetch two pages for variety
      for (const page of [1, 2]) {
        const res = await fetch(
          `https://api.themoviedb.org/3/discover/${endpoint}?api_key=${TMDB_KEY}&${dateParam}=2024-06-01&sort_by=popularity.desc&page=${page}&vote_count.gte=50`
        )
        const data = await res.json()
        for (const r of (data.results || []).slice(0, 15)) {
          const rawDate: string = r[dateKey] || ''
          const year = rawDate ? parseInt(rawDate.split('-')[0]) : null
          results.push({
            title: r[titleKey] as string,
            type: t,
            year,
            overview: ((r.overview as string) || '').slice(0, 120),
          })
        }
      }
    } catch {
      // skip on error
    }
  }

  return results
}

async function fetchRecentBooks(): Promise<Array<{ title: string; type: 'book'; year: number | null; overview: string }>> {
  try {
    const res = await fetch(
      'https://www.googleapis.com/books/v1/volumes?q=subject:fiction&orderBy=newest&maxResults=20&printType=books&langRestrict=en'
    )
    const data = await res.json()
    return ((data.items || []) as Array<{ volumeInfo: { title?: string; publishedDate?: string; description?: string } }>)
      .map(item => ({
        title: item.volumeInfo.title || '',
        type: 'book' as const,
        year: item.volumeInfo.publishedDate ? parseInt(item.volumeInfo.publishedDate.split('-')[0]) : null,
        overview: (item.volumeInfo.description || '').slice(0, 120),
      }))
      .filter(b => b.title && b.year && b.year >= 2024)
  } catch {
    return []
  }
}

export async function GET(req: NextRequest) {
  const telegramId = req.nextUrl.searchParams.get('telegram_id')
  const db = createServerClient()
  let query = db
    .from('recommendations')
    .select('*')
    .eq('dismissed', false)
    .order('created_at', { ascending: false })
    .limit(3)
  if (telegramId) query = query.eq('telegram_id', parseInt(telegramId))
  const { data } = await query
  return NextResponse.json(data || [])
}

export async function POST(req: NextRequest) {
  const { filters, telegram_id } = await req.json()
  const db = createServerClient()

  // Build taste profile from this user's library only
  let itemsQuery = db
    .from('items')
    .select('title, type, feeling, genres, vibe_tags, creator')
    .in('status', ['done', 'in_progress', 'abandoned'])
  if (telegram_id) itemsQuery = itemsQuery.eq('telegram_id', telegram_id)
  const { data: items } = await itemsQuery

  const loved = (items || []).filter(
    (i: { feeling: string }) => i.feeling === 'essential' || i.feeling === 'loved'
  )
  const disliked = (items || []).filter(
    (i: { feeling: string }) => i.feeling === 'not_for_me' || i.feeling === 'regret'
  )

  let dismissedQuery = db.from('recommendations').select('title').eq('dismissed', true)
  if (telegram_id) dismissedQuery = dismissedQuery.eq('telegram_id', telegram_id)
  const { data: dismissed } = await dismissedQuery

  const lovedList = loved
    .map((i: { title: string; type: string; genres?: string[]; vibe_tags?: string[] }) => {
      const parts = [`${i.title} (${i.type})`]
      if (i.genres?.length) parts.push(`genres: ${i.genres.slice(0, 3).join(', ')}`)
      if (i.vibe_tags?.length) parts.push(`vibes: ${i.vibe_tags.join(', ')}`)
      return parts.join(' — ')
    })
    .join('\n')

  const dislikedList = disliked.map((i: { title: string }) => i.title).join(', ')
  const dismissedList = (dismissed || []).map((d: { title: string }) => d.title).join(', ')

  const styleConstraint =
    filters.style === 'my_vibe'
      ? "Match their established taste closely — similar genres, tone, and vibe to what they've loved."
      : filters.style === 'out_of_lane'
      ? "Suggest something outside their usual genres — different territory they haven't explored but might enjoy."
      : 'No style constraint.'

  const intensityConstraint =
    filters.intensity === 'easy'
      ? 'Easy watch/read only: light, fun, accessible. No heavy tragedy, no slow burn, no arthouse.'
      : filters.intensity === 'demanding'
      ? 'Demanding content welcome: complex, challenging, slow burn, emotionally heavy, arthouse.'
      : 'No intensity constraint.'

  let prompt: string

  if (filters.new_only) {
    // Fetch real recent content from TMDB + Google Books
    const [recentMedia, recentBooks] = await Promise.all([
      fetchRecentFromTMDB(filters.type),
      filters.type === 'book' || !filters.type ? fetchRecentBooks() : Promise.resolve([]),
    ])

    const pool = filters.type === 'book'
      ? recentBooks
      : filters.type === 'film' || filters.type === 'show'
      ? recentMedia
      : [...recentMedia, ...recentBooks]

    const poolText = pool
      .map(r => `- ${r.title} (${r.type}, ${r.year}): ${r.overview}`)
      .join('\n')

    prompt = `You are recommending recent content to someone based on their taste.

Here are real recent 2024-2025 releases to choose from:
${poolText || 'No pool available — use your knowledge of 2024-2025 releases.'}

Their loved/essential items:
${lovedList || 'None logged yet'}

Their dislikes (avoid similar):
${dislikedList || 'None'}

Previously rejected (do NOT suggest):
${dismissedList || 'None'}

Filters:
- ${styleConstraint}
- ${intensityConstraint}

Pick the 3 BEST matches for this person from the pool above. Prefer items from the pool, but if the pool has fewer than 3 good matches, you may add well-known 2024-2025 releases not in the pool.

For each, write a "why" of up to 3 sentences — specific to this person's taste, not a generic description.

Return JSON array only:
[{"title": "...", "type": "film"|"show"|"book", "year": number|null, "creator": null, "why": "..."}]`

  } else {
    const typeConstraint = filters.type
      ? `Only suggest ${filters.type}s.`
      : 'Can suggest films, shows, or books — mix it up.'

    prompt = `You are recommending content to someone based on their personal taste.

Their loved/essential items:
${lovedList || 'None logged yet — use general taste signals if available'}

Their dislikes (avoid similar content):
${dislikedList || 'None'}

Previously rejected recommendations (do NOT suggest these):
${dismissedList || 'None'}

Constraints:
- ${typeConstraint}
- ${styleConstraint}
- ${intensityConstraint}

Generate exactly 3 recommendations. For each, write a "why" of up to 3 sentences — specific to this person's taste, not a generic description.

Return JSON array only, no other text:
[{"title": "...", "type": "film"|"show"|"book", "year": number|null, "creator": "...", "why": "..."}]`
  }

  const response = await client.messages.create({
    model: 'claude-sonnet-4-6',
    max_tokens: 900,
    messages: [{ role: 'user', content: prompt }],
  })

  let recs: Array<{ title: string; type: string; year: number | null; creator: string; why: string }>
  try {
    let text = (response.content[0] as { text: string }).text.trim()
    if (text.startsWith('```')) {
      text = text.replace(/^```[^\n]*\n/, '').replace(/```$/, '').trim()
    }
    recs = JSON.parse(text)
  } catch {
    return NextResponse.json({ error: 'Failed to parse recommendations' }, { status: 500 })
  }

  // Translate all "why" texts to Russian in one call
  let whyRuList: string[] = []
  try {
    const translateRes = await client.messages.create({
      model: 'claude-haiku-4-5-20251001',
      max_tokens: 600,
      messages: [{
        role: 'user',
        content: `Translate these recommendation descriptions to Russian. Keep the same casual, personal tone. Return JSON array of strings only:\n${JSON.stringify(recs.map(r => r.why))}`,
      }],
    })
    let tText = (translateRes.content[0] as { text: string }).text.trim()
    if (tText.startsWith('```')) tText = tText.replace(/^```[^\n]*\n/, '').replace(/```$/, '').trim()
    whyRuList = JSON.parse(tText)
  } catch {
    whyRuList = []
  }

  // Clear previous non-dismissed recommendations for this user
  let deleteQuery = db.from('recommendations').delete().eq('dismissed', false)
  if (telegram_id) deleteQuery = deleteQuery.eq('telegram_id', telegram_id)
  await deleteQuery

  // Enrich with TMDB and save
  const saved = []
  for (let i = 0; i < recs.length; i++) {
    const rec = recs[i]
    const enriched =
      rec.type === 'film' || rec.type === 'show'
        ? await enrichWithTMDB(rec.title, rec.type as 'film' | 'show')
        : {}

    const finalYear = enriched.year || rec.year || null

    const { data: inserted } = await db
      .from('recommendations')
      .insert({
        title: rec.title,
        title_ru: enriched.title_ru || null,
        type: rec.type,
        creator: enriched.creator || rec.creator || null,
        year: finalYear,
        cover_url: enriched.cover_url || null,
        description: enriched.description || null,
        genres: enriched.genres || null,
        why: rec.why,
        why_ru: whyRuList[i] || null,
        filters,
        telegram_id: telegram_id || null,
      })
      .select()
      .single()

    if (inserted) saved.push(inserted)
  }

  return NextResponse.json(saved)
}
