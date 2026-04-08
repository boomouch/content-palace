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

const TYPE_LABEL: Record<string, string> = {
  book: 'Books',
  film: 'Films',
  show: 'Shows',
  other: 'Other',
}

const STATUS_LABEL: Record<string, string> = {
  in_progress: 'Current',
  done: 'Finished',
  abandoned: 'Dropped',
}

const FEELINGS = ['essential', 'loved', 'average', 'not_for_me', 'regret'] as const

// ── Multi-select pill toggle ──
function toggleSet(set: Set<string>, value: string): Set<string> {
  const next = new Set(set)
  if (next.has(value)) next.delete(value)
  else next.add(value)
  return next
}

// ── Filter row with label ──
function FilterRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 px-5 py-1.5">
      <span
        className="text-xs uppercase tracking-widest flex-shrink-0 w-14"
        style={{ color: 'var(--text2)' }}
      >
        {label}
      </span>
      <div className="flex gap-1.5 overflow-x-auto pb-0.5" style={{ scrollbarWidth: 'none' }}>
        {children}
      </div>
    </div>
  )
}

function Pill({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className="flex-shrink-0 text-xs font-medium px-2.5 py-1 rounded-full transition-colors whitespace-nowrap"
      style={{
        background: active ? 'var(--accent-dim)' : 'transparent',
        color: active ? 'var(--accent)' : 'var(--text2)',
        border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
      }}
    >
      {children}
    </button>
  )
}

// ── Item card ──
function ItemCard({ item, onClick }: { item: Item; onClick: () => void }) {
  const emoji = item.feeling ? FEELING_EMOJI[item.feeling] : null
  return (
    <button
      onClick={onClick}
      className="w-full text-left rounded-lg overflow-hidden transition-transform active:scale-[0.97]"
      style={{ background: 'var(--surface)', border: '1px solid var(--border-dark)' }}
    >
      <div className="w-full overflow-hidden relative" style={{ aspectRatio: '2/3' }}>
        {item.cover_url ? (
          <img src={item.cover_url} alt={item.title} className="w-full h-full object-cover" />
        ) : (
          <div
            className="w-full h-full flex items-center justify-center text-xl"
            style={{ background: 'var(--surface2)' }}
          >
            {TYPE_ICON[item.type] || '◆'}
          </div>
        )}
        {emoji && (
          <span
            className="absolute bottom-1.5 right-1.5 text-sm leading-none px-1 py-0.5 rounded-md"
            style={{ background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(2px)' }}
          >
            {emoji}
          </span>
        )}
      </div>
      <div className="p-2">
        <h3
          className="font-medium text-xs leading-snug line-clamp-2"
          style={{ color: 'var(--text-on-dark)' }}
        >
          {item.title}
        </h3>
        {item.year && (
          <p className="text-xs mt-0.5" style={{ color: 'var(--text2-dark)' }}>
            {item.year}
          </p>
        )}
      </div>
    </button>
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
      <div className="fixed inset-0 z-40" style={{ background: 'rgba(0,0,0,0.65)' }} onClick={onClose} />
      <div
        className="fixed bottom-0 left-0 right-0 z-50 rounded-t-2xl overflow-y-auto"
        style={{ background: 'var(--surface)', maxHeight: '88vh' }}
      >
        <div className="p-5">
          <div className="w-10 h-1 rounded-full mx-auto mb-5" style={{ background: 'var(--border-dark)' }} />

          <div className="flex gap-4 mb-5">
            {item.cover_url && (
              <img
                src={item.cover_url}
                alt={item.title}
                className="flex-shrink-0 w-20 rounded-lg object-cover"
                style={{ aspectRatio: '2/3' }}
              />
            )}
            <div className="flex-1 min-w-0">
              <p className="text-xs mb-1" style={{ color: 'var(--text2-dark)' }}>
                {TYPE_ICON[item.type]} {item.type}{item.year ? ` · ${item.year}` : ''}
              </p>
              <h2
                className="font-bold text-lg leading-tight mb-1"
                style={{ color: 'var(--text-on-dark)', fontFamily: "'DM Serif Display', serif" }}
              >
                {item.title}
              </h2>
              {item.creator && (
                <p className="text-sm mb-2" style={{ color: 'var(--chip-text)' }}>{item.creator}</p>
              )}
              <div className="flex flex-wrap gap-2">
                {item.feeling && (
                  <span
                    className="text-xs px-2 py-0.5 rounded-full font-medium"
                    style={{ background: 'rgba(201,146,42,0.25)', color: 'var(--accent)' }}
                  >
                    {FEELING_LABEL[item.feeling]}
                  </span>
                )}
                {item.would_revisit && (
                  <span
                    className="text-xs px-2 py-0.5 rounded-full"
                    style={{ background: 'var(--surface2)', color: 'var(--chip-text)' }}
                  >
                    {REVISIT_LABEL[item.would_revisit]}
                  </span>
                )}
              </div>
            </div>
          </div>

          {item.highlight_quote && (
            <blockquote
              className="mb-5 pl-3 italic text-sm leading-relaxed"
              style={{ borderLeft: '2px solid var(--accent)', color: 'var(--text-on-dark)' }}
            >
              &ldquo;{item.highlight_quote}&rdquo;
            </blockquote>
          )}

          {highlights.length > 0 && (
            <div className="mb-5">
              <p className="text-xs uppercase tracking-widest mb-3" style={{ color: 'var(--text2-dark)' }}>Thoughts</p>
              <ul className="space-y-2">
                {highlights.map((h, i) => (
                  <li key={i} className="flex gap-2 text-sm" style={{ color: 'var(--text-on-dark)' }}>
                    <span style={{ color: 'var(--accent)', flexShrink: 0 }}>·</span>
                    {h}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {!highlights.length && item.summary && (
            <div className="mb-5">
              <p className="text-xs uppercase tracking-widest mb-2" style={{ color: 'var(--text2-dark)' }}>Thoughts</p>
              <p className="text-sm leading-relaxed" style={{ color: 'var(--text-on-dark)' }}>{item.summary}</p>
            </div>
          )}

          {item.vibe_tags && item.vibe_tags.length > 0 && (
            <div className="mb-5">
              <p className="text-xs uppercase tracking-widest mb-2" style={{ color: 'var(--text2-dark)' }}>Vibes</p>
              <div className="flex flex-wrap gap-2">
                {item.vibe_tags.map((tag) => (
                  <span key={tag} className="text-xs px-2 py-1 rounded-lg" style={{ background: 'var(--surface2)', color: 'var(--chip-text)' }}>{tag}</span>
                ))}
              </div>
            </div>
          )}

          {item.genres && item.genres.length > 0 && (
            <div className="mb-5">
              <p className="text-xs uppercase tracking-widest mb-2" style={{ color: 'var(--text2-dark)' }}>Genres</p>
              <div className="flex flex-wrap gap-2">
                {item.genres.map((g) => (
                  <span key={g} className="text-xs px-2 py-1 rounded-lg" style={{ background: 'var(--surface2)', color: 'var(--chip-text)' }}>{g}</span>
                ))}
              </div>
            </div>
          )}

          {item.description && (
            <div className="mb-5">
              <p className="text-xs uppercase tracking-widest mb-2" style={{ color: 'var(--text2-dark)' }}>About</p>
              <p className="text-sm leading-relaxed" style={{ color: 'var(--chip-text)' }}>{item.description}</p>
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
  const rated = items.filter((i) => i.feeling)
  const loved = items.filter((i) => i.feeling === 'essential' || i.feeling === 'loved')

  // Counts by type
  const byType = ['book', 'film', 'show', 'other'].map((t) => ({
    type: t,
    count: items.filter((i) => i.type === t).length,
  })).filter((x) => x.count > 0)

  // Rating distribution
  const byFeeling = FEELINGS.map((f) => ({
    feeling: f,
    count: rated.filter((i) => i.feeling === f).length,
  })).filter((x) => x.count > 0)
  const maxFeelingCount = Math.max(...byFeeling.map((x) => x.count), 1)

  // Top genres from loved/essential items
  const genreMap: Record<string, number> = {}
  loved.forEach((item) => {
    (item.genres || []).forEach((g) => {
      genreMap[g] = (genreMap[g] || 0) + 1
    })
  })
  const topGenres = Object.entries(genreMap)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([g]) => g)

  // Top vibe tags from loved/essential items
  const vibeMap: Record<string, number> = {}
  loved.forEach((item) => {
    (item.vibe_tags || []).forEach((t) => {
      vibeMap[t] = (vibeMap[t] || 0) + 1
    })
  })
  const topVibes = Object.entries(vibeMap)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 12)
    .map(([t]) => t)

  // Favourite creators (2+ rated items)
  const creatorMap: Record<string, number> = {}
  rated.forEach((item) => {
    if (item.creator) creatorMap[item.creator] = (creatorMap[item.creator] || 0) + 1
  })
  const topCreators = Object.entries(creatorMap)
    .filter(([, count]) => count >= 2)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-center px-5">
        <p className="text-4xl mb-4">🏰</p>
        <p style={{ color: 'var(--text2)' }}>Your palace is empty</p>
        <p className="text-sm mt-1" style={{ color: 'var(--text2)' }}>Add something via Telegram to see your taste profile</p>
      </div>
    )
  }

  return (
    <div className="px-5 pt-4 space-y-7 pb-10">

      {/* Summary row */}
      <div className="flex gap-3 flex-wrap">
        <div className="rounded-xl px-4 py-3 flex-1 min-w-0 text-center" style={{ background: 'var(--surface)' }}>
          <p className="text-2xl font-bold" style={{ color: 'var(--text-on-dark)' }}>{items.length}</p>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text2-dark)' }}>Total</p>
        </div>
        {byType.map(({ type, count }) => (
          <div key={type} className="rounded-xl px-4 py-3 flex-1 min-w-0 text-center" style={{ background: 'var(--surface)' }}>
            <p className="text-2xl font-bold" style={{ color: 'var(--text-on-dark)' }}>{count}</p>
            <p className="text-xs mt-0.5" style={{ color: 'var(--text2-dark)' }}>{TYPE_ICON[type]}</p>
          </div>
        ))}
      </div>

      {/* Rating distribution */}
      {byFeeling.length > 0 && (
        <div>
          <p className="text-xs uppercase tracking-widest mb-3" style={{ color: 'var(--text2)' }}>Ratings</p>
          <div className="space-y-2.5">
            {byFeeling.map(({ feeling, count }) => (
              <div key={feeling} className="flex items-center gap-3">
                <span className="text-base w-6 flex-shrink-0">{FEELING_EMOJI[feeling]}</span>
                <div className="flex-1 rounded-full overflow-hidden h-2" style={{ background: 'var(--surface)' }}>
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${(count / maxFeelingCount) * 100}%`,
                      background: 'var(--accent)',
                    }}
                  />
                </div>
                <span className="text-xs w-4 text-right flex-shrink-0" style={{ color: 'var(--text2-dark)' }}>{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Top genres */}
      {topGenres.length > 0 && (
        <div>
          <p className="text-xs uppercase tracking-widest mb-3" style={{ color: 'var(--text2)' }}>
            Favourite genres
          </p>
          <div className="flex flex-wrap gap-2">
            {topGenres.map((g) => (
              <span key={g} className="text-xs px-2.5 py-1.5 rounded-lg capitalize" style={{ background: 'var(--surface)', color: 'var(--chip-text)' }}>
                {g}
              </span>
            ))}
          </div>
          <p className="text-xs mt-2" style={{ color: 'var(--text2-dark)' }}>From 🔥 and ❤️ items only</p>
        </div>
      )}

      {/* Vibe tags */}
      {topVibes.length > 0 && (
        <div>
          <p className="text-xs uppercase tracking-widest mb-3" style={{ color: 'var(--text2)' }}>Your vibes</p>
          <div className="flex flex-wrap gap-2">
            {topVibes.map((t) => (
              <span key={t} className="text-xs px-2.5 py-1.5 rounded-lg" style={{ background: 'var(--surface)', color: 'var(--chip-text)' }}>
                {t}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Favourite creators */}
      {topCreators.length > 0 && (
        <div>
          <p className="text-xs uppercase tracking-widest mb-3" style={{ color: 'var(--text2)' }}>Creators you keep coming back to</p>
          <div className="space-y-2">
            {topCreators.map(([creator, count]) => (
              <div key={creator} className="flex items-center justify-between px-3 py-2 rounded-lg" style={{ background: 'var(--surface)' }}>
                <span className="text-sm" style={{ color: 'var(--text-on-dark)' }}>{creator}</span>
                <span className="text-xs" style={{ color: 'var(--accent)' }}>×{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {rated.length === 0 && (
        <p className="text-sm text-center py-4" style={{ color: 'var(--text2)' }}>
          Rate some items via Telegram to see your taste profile
        </p>
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

  // Fetch library/want items
  useEffect(() => {
    if (tab === 'profile') return
    async function load() {
      setLoading(true)

      let statuses: string[]
      if (tab === 'want') {
        statuses = ['want']
      } else if (statusFilters.size > 0) {
        statuses = [...statusFilters]
      } else {
        statuses = ['done', 'in_progress', 'abandoned']
      }

      let query = supabase
        .from('items')
        .select('*')
        .in('status', statuses)
        .order('added_at', { ascending: false })

      if (typeFilters.size > 0) {
        query = query.in('type', [...typeFilters])
      }

      if (tab === 'library' && feelingFilters.size > 0) {
        query = query.in('feeling', [...feelingFilters])
      }

      const { data } = await query
      setItems(data || [])
      setLoading(false)
    }
    load()
  }, [tab, typeFilters, statusFilters, feelingFilters])

  // Fetch all items for profile tab
  useEffect(() => {
    if (tab !== 'profile') return
    async function loadAll() {
      setLoading(true)
      const { data } = await supabase
        .from('items')
        .select('*')
        .in('status', ['done', 'in_progress', 'abandoned'])
        .order('added_at', { ascending: false })
      setAllItems(data || [])
      setLoading(false)
    }
    loadAll()
  }, [tab])

  const showSections = tab === 'library' && statusFilters.size === 0
  const inProgress = items.filter((i) => i.status === 'in_progress')
  const finished = items.filter((i) => i.status === 'done' || i.status === 'abandoned')

  function switchTab(t: 'library' | 'want' | 'profile') {
    setTab(t)
    setStatusFilters(new Set())
    setFeelingFilters(new Set())
    setTypeFilters(new Set())
  }

  return (
    <div className="min-h-screen pb-24" style={{ background: 'var(--bg)' }}>
      {/* Header */}
      <header className="px-5 pt-12 pb-4">
        <h1 style={{ fontFamily: "'DM Serif Display', serif", fontSize: '2rem', color: 'var(--text)', lineHeight: 1.1 }}>
          Content Palace
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--text2)' }}>Your personal library</p>
      </header>

      {/* Tabs */}
      <div className="px-5 flex gap-0" style={{ borderBottom: '1px solid var(--border)' }}>
        {(['library', 'want', 'profile'] as const).map((t) => (
          <button
            key={t}
            onClick={() => switchTab(t)}
            className="px-4 py-2.5 text-sm font-medium relative capitalize"
            style={{ color: tab === t ? 'var(--text)' : 'var(--text2)' }}
          >
            {t === 'library' ? 'Library' : t === 'want' ? 'Want List' : 'Profile'}
            {tab === t && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 rounded-t" style={{ background: 'var(--accent)' }} />
            )}
          </button>
        ))}
      </div>

      {/* Filters (library + want only) */}
      {tab !== 'profile' && (
        <div className="pt-2 pb-1" style={{ borderBottom: '1px solid var(--border)' }}>
          {/* Type */}
          <FilterRow label="Type">
            <Pill active={typeFilters.size === 0} onClick={() => setTypeFilters(new Set())}>All</Pill>
            {(['book', 'film', 'show', 'other'] as const).map((t) => (
              <Pill key={t} active={typeFilters.has(t)} onClick={() => setTypeFilters(toggleSet(typeFilters, t))}>
                {TYPE_ICON[t]} {TYPE_LABEL[t]}
              </Pill>
            ))}
          </FilterRow>

          {/* Status (library only) */}
          {tab === 'library' && (
            <FilterRow label="Status">
              <Pill active={statusFilters.size === 0} onClick={() => setStatusFilters(new Set())}>All</Pill>
              {(['in_progress', 'done', 'abandoned'] as const).map((s) => (
                <Pill key={s} active={statusFilters.has(s)} onClick={() => setStatusFilters(toggleSet(statusFilters, s))}>
                  {STATUS_LABEL[s]}
                </Pill>
              ))}
            </FilterRow>
          )}

          {/* Rating (library only) */}
          {tab === 'library' && (
            <FilterRow label="Rating">
              <Pill active={feelingFilters.size === 0} onClick={() => setFeelingFilters(new Set())}>All</Pill>
              {FEELINGS.map((f) => (
                <button
                  key={f}
                  onClick={() => setFeelingFilters(toggleSet(feelingFilters, f))}
                  className="flex-shrink-0 text-base px-2 py-0.5 rounded-full transition-colors"
                  style={{
                    background: feelingFilters.has(f) ? 'var(--accent-dim)' : 'transparent',
                    border: `1px solid ${feelingFilters.has(f) ? 'var(--accent)' : 'var(--border)'}`,
                  }}
                >
                  {FEELING_EMOJI[f]}
                </button>
              ))}
            </FilterRow>
          )}
        </div>
      )}

      {/* Profile tab */}
      {tab === 'profile' && (
        loading ? (
          <div className="flex justify-center py-24">
            <div className="w-6 h-6 rounded-full border-2 animate-spin" style={{ borderColor: 'var(--border)', borderTopColor: 'var(--accent)' }} />
          </div>
        ) : (
          <ProfilePage items={allItems} />
        )
      )}

      {/* Library / Want content */}
      {tab !== 'profile' && (
        <div className="px-4 pt-3">
          {loading ? (
            <div className="flex justify-center py-24">
              <div className="w-6 h-6 rounded-full border-2 animate-spin" style={{ borderColor: 'var(--border)', borderTopColor: 'var(--accent)' }} />
            </div>
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-24 text-center">
              <p className="text-4xl mb-4">📚</p>
              <p style={{ color: 'var(--text2)' }}>{tab === 'want' ? 'Your want list is empty' : 'Nothing here yet'}</p>
              <p className="text-sm mt-1" style={{ color: 'var(--text2)' }}>Add something via Telegram</p>
            </div>
          ) : (
            <div className="space-y-6">
              {showSections && inProgress.length > 0 && (
                <section>
                  <p className="text-xs uppercase tracking-widest mb-3" style={{ color: 'var(--text2)' }}>Currently</p>
                  <div className="grid grid-cols-3 gap-2">
                    {inProgress.map((item) => (
                      <ItemCard key={item.id} item={item} onClick={() => setSelected(item)} />
                    ))}
                  </div>
                </section>
              )}

              {showSections && finished.length > 0 && (
                <section>
                  {inProgress.length > 0 && (
                    <p className="text-xs uppercase tracking-widest mb-3" style={{ color: 'var(--text2)' }}>Finished</p>
                  )}
                  <div className="grid grid-cols-3 gap-2">
                    {finished.map((item) => (
                      <ItemCard key={item.id} item={item} onClick={() => setSelected(item)} />
                    ))}
                  </div>
                </section>
              )}

              {!showSections && (
                <div className="grid grid-cols-3 gap-2">
                  {items.map((item) => (
                    <ItemCard key={item.id} item={item} onClick={() => setSelected(item)} />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {selected && <ItemDrawer item={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
