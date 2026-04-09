'use client'

import { useEffect, useState } from 'react'
import { supabase, Item } from '@/lib/supabase'

const FEELING_EMOJI: Record<string, string> = {
  essential: '🔥',
  loved: '❤️',
  average: '😐',
  not_for_me: '🙈',
  regret: '💀',
}

const FEELING_LABEL: Record<string, string> = {
  essential: '🔥 Essential',
  loved: '❤️ Loved it',
  average: '😐 Average',
  not_for_me: '🙈 Not for me',
  regret: '💀 Regret it',
}

const REVISIT_LABEL: Record<string, string> = {
  yes: '↩ Would revisit',
  maybe: '↩ Maybe revisit',
  no: '— Probably not',
}

const TYPE_ICON: Record<string, string> = {
  book: '📖',
  film: '🎬',
  show: '📺',
  other: '◆',
}

const SUBTYPE_LABEL: Record<string, string> = {
  youtube: '▶ YouTube',
  podcast: '🎙 Podcast',
  newsletter: '✉ Newsletter',
  article: '📄 Article',
  blog: '✏ Blog',
  documentary: '🎞 Documentary',
  course: '📐 Course',
}

const TYPE_LABEL: Record<string, string> = {
  book: 'Books',
  film: 'Films',
  show: 'Shows',
  other: 'Others',
}

const STATUS_LABEL: Record<string, string> = {
  in_progress: 'Current',
  done: 'Finished',
  abandoned: 'Dropped',
}

const FEELINGS = ['essential', 'loved', 'average', 'not_for_me', 'regret'] as const

function toggleSet(set: Set<string>, value: string): Set<string> {
  const next = new Set(set)
  if (next.has(value)) next.delete(value)
  else next.add(value)
  return next
}

// ── SVG Icons ──
function IconGrid({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2.5" y="2.5" width="6" height="6" rx="1"/>
      <rect x="11.5" y="2.5" width="6" height="6" rx="1"/>
      <rect x="2.5" y="11.5" width="6" height="6" rx="1"/>
      <rect x="11.5" y="11.5" width="6" height="6" rx="1"/>
    </svg>
  )
}

function IconBookmark({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 2.5h10a1 1 0 011 1v13.5l-6-3.75-6 3.75V3.5a1 1 0 011-1z"/>
    </svg>
  )
}

function IconPerson({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <circle cx="10" cy="7" r="3.5"/>
      <path d="M3 18c0-3.866 3.134-7 7-7s7 3.134 7 7"/>
    </svg>
  )
}

function IconSearch({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <circle cx="9" cy="9" r="5.5"/>
      <path d="M14 14l3.5 3.5"/>
    </svg>
  )
}

// ── Chip ──
function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className="flex-shrink-0 flex items-center gap-1 text-xs font-medium px-3 py-1.5 rounded-full whitespace-nowrap"
      style={{
        background: active ? 'var(--text)' : 'transparent',
        color: active ? 'var(--bg)' : 'var(--text2)',
        border: `1px solid ${active ? 'var(--text)' : 'var(--border)'}`,
      }}
    >
      {children}
    </button>
  )
}

// ── Featured card (currently reading/watching) ──
function FeaturedCard({ item, onClick }: { item: Item; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left rounded-2xl overflow-hidden flex transition-transform active:scale-[0.98]"
      style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', boxShadow: 'var(--card-shadow)' }}
    >
      <div style={{ width: '36%', flexShrink: 0 }}>
        <div className="w-full h-full" style={{ minHeight: '180px' }}>
          {item.cover_url ? (
            <img src={item.cover_url} alt={item.title} className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-3xl" style={{ background: 'var(--card-bg2)' }}>
              {TYPE_ICON[item.type] || '◆'}
            </div>
          )}
        </div>
      </div>
      <div className="flex-1 p-4 flex flex-col justify-between min-w-0">
        <div>
          {item.year && (
            <p className="text-xs mb-1.5 tabular-nums" style={{ color: 'var(--text2)' }}>{item.year}</p>
          )}
          <h3
            className="font-bold leading-tight mb-1.5"
            style={{ fontFamily: "'DM Serif Display', serif", fontSize: '1.25rem', color: 'var(--text)' }}
          >
            {item.title}
          </h3>
          {item.creator && (
            <p className="text-sm mb-3" style={{ color: 'var(--text2)' }}>{item.creator}</p>
          )}
          <span
            className="inline-flex items-center text-xs font-bold tracking-wider px-2.5 py-1 rounded-full"
            style={{ background: 'var(--text)', color: 'var(--bg)' }}
          >
            CURRENT
          </span>
        </div>
        {item.highlight_quote && (
          <p className="text-xs italic mt-4 leading-relaxed line-clamp-3" style={{ color: 'var(--text2)' }}>
            &ldquo;{item.highlight_quote}&rdquo;
          </p>
        )}
      </div>
    </button>
  )
}

// ── Item card (grid) ──
function ItemCard({ item, onClick }: { item: Item; onClick: () => void }) {
  const emoji = item.feeling ? FEELING_EMOJI[item.feeling] : null
  return (
    <button
      onClick={onClick}
      className="w-full text-left rounded-xl overflow-hidden transition-transform active:scale-[0.97]"
      style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', boxShadow: 'var(--card-shadow)' }}
    >
      <div className="w-full overflow-hidden" style={{ aspectRatio: '2/3' }}>
        {item.cover_url ? (
          <img src={item.cover_url} alt={item.title} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-2xl" style={{ background: 'var(--card-bg2)' }}>
            {TYPE_ICON[item.type] || '◆'}
          </div>
        )}
      </div>
      <div className="p-2">
        <h3 className="font-medium text-xs leading-snug line-clamp-2" style={{ color: 'var(--text)' }}>
          {emoji && <span className="mr-0.5">{emoji}</span>}
          {item.title}
        </h3>
        {(item.subtype || item.year) && (
          <p className="text-xs mt-0.5 tabular-nums" style={{ color: 'var(--text2)' }}>
            {item.subtype ? (SUBTYPE_LABEL[item.subtype] ?? item.subtype) : item.year}
          </p>
        )}
      </div>
    </button>
  )
}

// ── Section header ──
function SectionHeader({ title }: { title: string }) {
  return (
    <h2 className="text-xs font-bold tracking-widest uppercase mb-3" style={{ color: 'var(--text)' }}>
      {title}
    </h2>
  )
}

// ── Item drawer ──
function ItemDrawer({ item, onClose }: { item: Item; onClose: () => void }) {
  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [])

  const highlights: string[] = (() => {
    if (!item.summary) return []
    try {
      const parsed = JSON.parse(item.summary)
      if (Array.isArray(parsed)) return parsed
    } catch {}
    return []
  })()

  return (
    <>
      <div className="fixed inset-0 z-40" style={{ background: 'rgba(0,0,0,0.35)' }} onClick={onClose} />
      <div
        className="fixed bottom-0 left-0 right-0 z-50 rounded-t-2xl overflow-y-auto"
        style={{ background: 'var(--card-bg)', maxHeight: '88vh' }}
      >
        <div className="p-5">
          <div className="w-8 h-1 rounded-full mx-auto mb-5" style={{ background: 'var(--border)' }} />

          <div className="flex gap-4 mb-5">
            {item.cover_url && (
              <img
                src={item.cover_url}
                alt={item.title}
                className="flex-shrink-0 w-20 rounded-xl object-cover"
                style={{ aspectRatio: '2/3' }}
              />
            )}
            <div className="flex-1 min-w-0">
              <p className="text-xs mb-1" style={{ color: 'var(--text2)' }}>
                {item.subtype ? SUBTYPE_LABEL[item.subtype] ?? item.subtype : `${TYPE_ICON[item.type]} ${item.type}`}
                {item.year ? ` · ${item.year}` : ''}
              </p>
              <h2
                className="font-bold text-xl leading-tight mb-1"
                style={{ color: 'var(--text)', fontFamily: "'DM Serif Display', serif" }}
              >
                {item.title}
              </h2>
              {item.creator && (
                <p className="text-sm mb-2" style={{ color: 'var(--text2)' }}>{item.creator}</p>
              )}
              <div className="flex flex-wrap gap-2">
                {item.feeling && (
                  <span
                    className="text-xs px-2.5 py-1 rounded-full font-medium"
                    style={{ background: 'var(--accent-dim)', color: 'var(--accent)' }}
                  >
                    {FEELING_LABEL[item.feeling]}
                  </span>
                )}
                {item.would_revisit && (
                  <span
                    className="text-xs px-2.5 py-1 rounded-full"
                    style={{ background: 'var(--card-bg2)', color: 'var(--chip-text)', border: '1px solid var(--border)' }}
                  >
                    {REVISIT_LABEL[item.would_revisit]}
                  </span>
                )}
              </div>
              {(item.started_at || item.finished_at) && (
                <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2">
                  {item.started_at && (
                    <span className="text-xs" style={{ color: 'var(--text2)' }}>
                      Started {new Date(item.started_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
                    </span>
                  )}
                  {item.finished_at && (
                    <span className="text-xs" style={{ color: 'var(--text2)' }}>
                      {item.status === 'abandoned' ? 'Abandoned' : 'Finished'} {new Date(item.finished_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>

          {item.highlight_quote && (
            <blockquote
              className="mb-5 pl-4 italic text-sm leading-relaxed"
              style={{ borderLeft: '2px solid var(--accent)', color: 'var(--text)' }}
            >
              &ldquo;{item.highlight_quote}&rdquo;
            </blockquote>
          )}

          {highlights.length > 0 && (
            <div className="mb-5">
              <p className="text-xs uppercase tracking-widest mb-3" style={{ color: 'var(--text2)' }}>Thoughts</p>
              <ul className="space-y-2">
                {highlights.map((h, i) => (
                  <li key={i} className="flex gap-2 text-sm" style={{ color: 'var(--text)' }}>
                    <span style={{ color: 'var(--accent)', flexShrink: 0 }}>·</span>
                    {h}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {!highlights.length && item.summary && (
            <div className="mb-5">
              <p className="text-xs uppercase tracking-widest mb-2" style={{ color: 'var(--text2)' }}>Thoughts</p>
              <p className="text-sm leading-relaxed" style={{ color: 'var(--text)' }}>{item.summary}</p>
            </div>
          )}

          {item.vibe_tags && item.vibe_tags.length > 0 && (
            <div className="mb-5">
              <p className="text-xs uppercase tracking-widest mb-2" style={{ color: 'var(--text2)' }}>Vibes</p>
              <div className="flex flex-wrap gap-2">
                {item.vibe_tags.map((tag) => (
                  <span key={tag} className="text-xs px-2.5 py-1 rounded-lg" style={{ background: 'var(--card-bg2)', color: 'var(--chip-text)', border: '1px solid var(--border)' }}>{tag}</span>
                ))}
              </div>
            </div>
          )}

          {item.genres && item.genres.length > 0 && (
            <div className="mb-5">
              <p className="text-xs uppercase tracking-widest mb-2" style={{ color: 'var(--text2)' }}>Genres</p>
              <div className="flex flex-wrap gap-2">
                {item.genres.map((g) => (
                  <span key={g} className="text-xs px-2.5 py-1 rounded-lg capitalize" style={{ background: 'var(--card-bg2)', color: 'var(--chip-text)', border: '1px solid var(--border)' }}>{g}</span>
                ))}
              </div>
            </div>
          )}

          {item.description && (
            <div className="mb-5">
              <p className="text-xs uppercase tracking-widest mb-2" style={{ color: 'var(--text2)' }}>About</p>
              <p className="text-sm leading-relaxed" style={{ color: 'var(--text2)' }}>{item.description}</p>
            </div>
          )}

          <div className="h-6" />
        </div>
      </div>
    </>
  )
}

// ── Profile tab ──
function ProfilePage({ items }: { items: Item[] }) {
  const [tasteSummary, setTasteSummary] = useState<string | null>(null)
  const [summaryLoading, setSummaryLoading] = useState(false)

  const rated = items.filter((i) => i.feeling)
  const loved = items.filter((i) => i.feeling === 'essential' || i.feeling === 'loved')

  const byType = ['book', 'film', 'show', 'other'].map((t) => ({
    type: t, count: items.filter((i) => i.type === t).length,
  })).filter((x) => x.count > 0)

  const byFeeling = FEELINGS.map((f) => ({
    feeling: f, count: rated.filter((i) => i.feeling === f).length,
  })).filter((x) => x.count > 0)
  const maxFeelingCount = Math.max(...byFeeling.map((x) => x.count), 1)

  const genreMap: Record<string, number> = {}
  loved.forEach((item) => { (item.genres || []).forEach((g) => { genreMap[g] = (genreMap[g] || 0) + 1 }) })
  const topGenres = Object.entries(genreMap).sort((a, b) => b[1] - a[1]).slice(0, 10).map(([g]) => g)

  const vibeMap: Record<string, number> = {}
  loved.forEach((item) => { (item.vibe_tags || []).forEach((t) => { vibeMap[t] = (vibeMap[t] || 0) + 1 }) })
  const topVibes = Object.entries(vibeMap).sort((a, b) => b[1] - a[1]).slice(0, 12).map(([t]) => t)

  const creatorMap: Record<string, number> = {}
  rated.forEach((item) => { if (item.creator) creatorMap[item.creator] = (creatorMap[item.creator] || 0) + 1 })
  const topCreators = Object.entries(creatorMap).filter(([, c]) => c >= 2).sort((a, b) => b[1] - a[1]).slice(0, 6)

  useEffect(() => {
    if (rated.length < 3) return
    setSummaryLoading(true)
    fetch('/api/taste-summary', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        total: items.length,
        byType: Object.fromEntries(byType.map(({ type, count }) => [type, count])),
        topGenres,
        topVibes,
        byFeeling: Object.fromEntries(byFeeling.map(({ feeling, count }) => [feeling, count])),
        topCreators,
      }),
    })
      .then((r) => r.json())
      .then((d) => setTasteSummary(d.summary))
      .finally(() => setSummaryLoading(false))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-center px-5">
        <p className="text-4xl mb-4">🏰</p>
        <p style={{ color: 'var(--text2)' }}>Your palace is empty</p>
        <p className="text-sm mt-1" style={{ color: 'var(--text2)' }}>Add something via Telegram to see your profile</p>
      </div>
    )
  }

  return (
    <div className="px-4 pt-5 space-y-7 pb-4">

      {/* AI taste summary */}
      <div className="rounded-2xl p-4" style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', boxShadow: 'var(--card-shadow)' }}>
        <p className="text-xs uppercase tracking-widest mb-3 font-bold" style={{ color: 'var(--text2)' }}>Your taste</p>
        {summaryLoading ? (
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full border-2 animate-spin flex-shrink-0" style={{ borderColor: 'var(--border)', borderTopColor: 'var(--accent)' }} />
            <p className="text-sm" style={{ color: 'var(--text2)' }}>Thinking...</p>
          </div>
        ) : tasteSummary ? (
          <p className="leading-relaxed" style={{ color: 'var(--text)', fontFamily: "'DM Serif Display', serif", fontSize: '1.05rem' }}>
            {tasteSummary}
          </p>
        ) : (
          <p className="text-sm" style={{ color: 'var(--text2)' }}>
            Rate at least 3 items via Telegram to unlock your taste profile.
          </p>
        )}
      </div>

      {/* Counts */}
      <div className="grid grid-cols-4 gap-2">
        {byType.map(({ type, count }) => (
          <div key={type} className="rounded-xl py-3 text-center" style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', boxShadow: 'var(--card-shadow)' }}>
            <p className="text-lg">{TYPE_ICON[type]}</p>
            <p className="text-lg font-bold mt-0.5" style={{ color: 'var(--text)' }}>{count}</p>
          </div>
        ))}
      </div>

      {/* Rating distribution */}
      {byFeeling.length > 0 && (
        <div>
          <p className="text-xs uppercase tracking-widest mb-3 font-bold" style={{ color: 'var(--text2)' }}>Ratings</p>
          <div className="space-y-2.5">
            {byFeeling.map(({ feeling, count }) => (
              <div key={feeling} className="flex items-center gap-3">
                <span className="text-base w-5 flex-shrink-0">{FEELING_EMOJI[feeling]}</span>
                <div className="flex-1 rounded-full overflow-hidden h-1.5" style={{ background: 'var(--border)' }}>
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${(count / maxFeelingCount) * 100}%`, background: 'var(--text)' }}
                  />
                </div>
                <span className="text-xs w-4 text-right flex-shrink-0 tabular-nums" style={{ color: 'var(--text2)' }}>{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Top genres */}
      {topGenres.length > 0 && (
        <div>
          <p className="text-xs uppercase tracking-widest mb-3 font-bold" style={{ color: 'var(--text2)' }}>Favourite genres</p>
          <div className="flex flex-wrap gap-2">
            {topGenres.map((g) => (
              <span key={g} className="text-xs px-3 py-1.5 rounded-full capitalize" style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', color: 'var(--chip-text)' }}>{g}</span>
            ))}
          </div>
        </div>
      )}

      {/* Vibe tags */}
      {topVibes.length > 0 && (
        <div>
          <p className="text-xs uppercase tracking-widest mb-3 font-bold" style={{ color: 'var(--text2)' }}>Your vibes</p>
          <div className="flex flex-wrap gap-2">
            {topVibes.map((t) => (
              <span key={t} className="text-xs px-3 py-1.5 rounded-full" style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', color: 'var(--chip-text)' }}>{t}</span>
            ))}
          </div>
        </div>
      )}

      {/* Favourite creators */}
      {topCreators.length > 0 && (
        <div>
          <p className="text-xs uppercase tracking-widest mb-3 font-bold" style={{ color: 'var(--text2)' }}>Creators you keep coming back to</p>
          <div className="space-y-1.5">
            {topCreators.map(([creator, count]) => (
              <div key={creator} className="flex items-center justify-between px-3 py-2.5 rounded-xl" style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', boxShadow: 'var(--card-shadow)' }}>
                <span className="text-sm" style={{ color: 'var(--text)' }}>{creator}</span>
                <span className="text-xs font-bold" style={{ color: 'var(--accent)' }}>×{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Main page ──
export default function Home() {
  const [tab, setTab] = useState<'library' | 'want' | 'profile'>('library')
  const [typeFilters, setTypeFilters] = useState<Set<string>>(new Set())
  const [statusFilters, setStatusFilters] = useState<Set<string>>(new Set())
  const [feelingFilters, setFeelingFilters] = useState<Set<string>>(new Set())
  const [items, setItems] = useState<Item[]>([])
  const [allItems, setAllItems] = useState<Item[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<Item | null>(null)

  useEffect(() => {
    if (tab === 'profile') return
    async function load() {
      setLoading(true)
      let statuses: string[]
      if (tab === 'want') statuses = ['want']
      else if (statusFilters.size > 0) statuses = [...statusFilters]
      else statuses = ['done', 'in_progress', 'abandoned']

      let query = supabase.from('items').select('*').in('status', statuses).order('added_at', { ascending: false })
      if (typeFilters.size > 0) query = query.in('type', [...typeFilters])
      if (tab === 'library' && feelingFilters.size > 0) query = query.in('feeling', [...feelingFilters])

      const { data } = await query
      setItems(data || [])
      setLoading(false)
    }
    load()
  }, [tab, typeFilters, statusFilters, feelingFilters])

  useEffect(() => {
    if (tab !== 'profile') return
    async function loadAll() {
      setLoading(true)
      const { data } = await supabase.from('items').select('*').in('status', ['done', 'in_progress', 'abandoned']).order('added_at', { ascending: false })
      setAllItems(data || [])
      setLoading(false)
    }
    loadAll()
  }, [tab])

  const [showAllFinished, setShowAllFinished] = useState(false)

  const showSections = tab === 'library' && statusFilters.size === 0
  const inProgress = items.filter((i) => i.status === 'in_progress')
  const finished = items.filter((i) => i.status === 'done' || i.status === 'abandoned')
  const FINISHED_LIMIT = 9
  const visibleFinished = showAllFinished ? finished : finished.slice(0, FINISHED_LIMIT)

  function switchTab(t: 'library' | 'want' | 'profile') {
    setTab(t)
    setStatusFilters(new Set())
    setFeelingFilters(new Set())
    setTypeFilters(new Set())
  }

  const PAGE_TITLES: Record<string, string> = {
    library: 'LIBRARY',
    want: 'WANT LIST',
    profile: 'PROFILE',
  }

  const PAGE_SUBTITLES: Record<string, string> = {
    library: 'Your personal library',
    want: 'Things to read & watch',
    profile: 'Your taste in numbers',
  }

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg)', paddingBottom: '72px' }}>

      {/* Top bar */}
      <header className="flex items-center justify-between px-5 pt-12 pb-4">
        <span className="text-xs font-bold tracking-widest uppercase" style={{ color: 'var(--text)' }}>
          CONTENT PALACE <span style={{ color: 'var(--accent)' }}>•</span>
        </span>
        <button style={{ color: 'var(--text2)' }}>
          <IconSearch size={18} />
        </button>
      </header>

      {/* Page title */}
      <div className="px-5 pb-4">
        <h1
          className="font-black uppercase leading-none"
          style={{ fontSize: '2.6rem', letterSpacing: '-0.01em', color: 'var(--text)' }}
        >
          {PAGE_TITLES[tab]}
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--text2)' }}>{PAGE_SUBTITLES[tab]}</p>
      </div>

      {/* Filters */}
      {tab !== 'profile' && (
        <div className="pb-3" style={{ borderBottom: '1px solid var(--border)' }}>
          {/* Type filter */}
          <div className="flex gap-2 px-5 pb-2 overflow-x-auto" style={{ scrollbarWidth: 'none' }}>
            <Chip active={typeFilters.size === 0} onClick={() => setTypeFilters(new Set())}>
              <IconGrid size={11} /> ALL
            </Chip>
            {(['book', 'film', 'show', 'other'] as const).map((t) => (
              <Chip key={t} active={typeFilters.has(t)} onClick={() => setTypeFilters(toggleSet(typeFilters, t))}>
                <span className="text-xs">{TYPE_ICON[t]}</span> {TYPE_LABEL[t].toUpperCase()}
              </Chip>
            ))}
          </div>

          {/* Status + rating filter */}
          {tab === 'library' && (
            <div className="flex gap-2 px-5 overflow-x-auto" style={{ scrollbarWidth: 'none' }}>
              <Chip active={statusFilters.size === 0 && feelingFilters.size === 0} onClick={() => { setStatusFilters(new Set()); setFeelingFilters(new Set()) }}>
                ALL
              </Chip>
              {(['in_progress', 'done', 'abandoned'] as const).map((s) => (
                <Chip key={s} active={statusFilters.has(s)} onClick={() => setStatusFilters(toggleSet(statusFilters, s))}>
                  {STATUS_LABEL[s].toUpperCase()}
                </Chip>
              ))}
              <div className="w-px self-stretch flex-shrink-0" style={{ background: 'var(--border)' }} />
              {FEELINGS.map((f) => (
                <button
                  key={f}
                  onClick={() => setFeelingFilters(toggleSet(feelingFilters, f))}
                  className="flex-shrink-0 text-sm px-2.5 py-1.5 rounded-full"
                  style={{
                    background: feelingFilters.has(f) ? 'var(--text)' : 'transparent',
                    border: `1px solid ${feelingFilters.has(f) ? 'var(--text)' : 'var(--border)'}`,
                  }}
                >
                  {FEELING_EMOJI[f]}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Content */}
      {tab === 'profile' ? (
        loading ? (
          <div className="flex justify-center py-24">
            <div className="w-5 h-5 rounded-full border-2 animate-spin" style={{ borderColor: 'var(--border)', borderTopColor: 'var(--text)' }} />
          </div>
        ) : (
          <ProfilePage items={allItems} />
        )
      ) : (
        <div className="px-4 pt-4">
          {loading ? (
            <div className="flex justify-center py-24">
              <div className="w-5 h-5 rounded-full border-2 animate-spin" style={{ borderColor: 'var(--border)', borderTopColor: 'var(--text)' }} />
            </div>
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-24 text-center">
              <p className="text-4xl mb-4">{tab === 'want' ? '🔖' : '📚'}</p>
              <p style={{ color: 'var(--text2)' }}>{tab === 'want' ? 'Nothing saved yet' : 'Nothing here yet'}</p>
              <p className="text-sm mt-1" style={{ color: 'var(--text2)' }}>Add something via Telegram</p>
            </div>
          ) : (
            <div className="space-y-6">
              {showSections && inProgress.length > 0 && (
                <section>
                  <SectionHeader title="Currently" />
                  <div
                    className="flex gap-3 overflow-x-auto pb-1"
                    style={{ scrollbarWidth: 'none', scrollSnapType: 'x mandatory' }}
                  >
                    {inProgress.map((item) => (
                      <div key={item.id} style={{ minWidth: '82vw', maxWidth: '82vw', scrollSnapAlign: 'start' }}>
                        <FeaturedCard item={item} onClick={() => setSelected(item)} />
                      </div>
                    ))}
                  </div>
                </section>
              )}
              {showSections && finished.length > 0 && (
                <section>
                  <SectionHeader title="Finished" />
                  <div className="grid grid-cols-3 gap-2.5">
                    {visibleFinished.map((item) => <ItemCard key={item.id} item={item} onClick={() => setSelected(item)} />)}
                  </div>
                  {finished.length > FINISHED_LIMIT && (
                    <button
                      onClick={() => setShowAllFinished(!showAllFinished)}
                      className="w-full mt-3 py-2.5 text-xs font-medium tracking-wide uppercase rounded-xl"
                      style={{ border: '1px solid var(--border)', color: 'var(--text2)' }}
                    >
                      {showAllFinished ? 'Show less' : `Show all ${finished.length}`}
                    </button>
                  )}
                </section>
              )}
              {!showSections && (
                <div className="grid grid-cols-3 gap-2.5">
                  {items.map((item) => <ItemCard key={item.id} item={item} onClick={() => setSelected(item)} />)}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Bottom navigation */}
      <nav
        className="fixed bottom-0 left-0 right-0 z-30 flex"
        style={{
          background: 'rgba(245,240,232,0.94)',
          backdropFilter: 'blur(16px)',
          borderTop: '1px solid var(--border)',
          paddingBottom: 'env(safe-area-inset-bottom)',
        }}
      >
        <button
          onClick={() => switchTab('library')}
          className="flex-1 flex flex-col items-center py-3 gap-1"
          style={{ color: tab === 'library' ? 'var(--text)' : 'var(--text2)' }}
        >
          <IconGrid size={20} />
          <span className="text-xs font-medium tracking-wide">LIBRARY</span>
        </button>
        <button
          onClick={() => switchTab('want')}
          className="flex-1 flex flex-col items-center py-3 gap-1"
          style={{ color: tab === 'want' ? 'var(--text)' : 'var(--text2)' }}
        >
          <IconBookmark size={20} />
          <span className="text-xs font-medium tracking-wide">WANT</span>
        </button>
        <button
          onClick={() => switchTab('profile')}
          className="flex-1 flex flex-col items-center py-3 gap-1"
          style={{ color: tab === 'profile' ? 'var(--text)' : 'var(--text2)' }}
        >
          <IconPerson size={20} />
          <span className="text-xs font-medium tracking-wide">PROFILE</span>
        </button>
      </nav>

      {selected && <ItemDrawer item={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
