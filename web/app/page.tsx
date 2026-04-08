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

const TYPES = ['all', 'book', 'film', 'show', 'other'] as const

const STATUS_FILTERS = ['all', 'in_progress', 'done', 'abandoned'] as const
const STATUS_LABEL: Record<string, string> = {
  all: 'All',
  in_progress: 'Current',
  done: 'Finished',
  abandoned: 'Dropped',
}

const FEELING_FILTERS = ['essential', 'loved', 'average', 'not_for_me', 'regret'] as const

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
            className="absolute bottom-1 right-1 text-sm leading-none"
            style={{ filter: 'drop-shadow(0 1px 3px rgba(0,0,0,0.9))' }}
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
      <div
        className="fixed inset-0 z-40"
        style={{ background: 'rgba(0,0,0,0.65)' }}
        onClick={onClose}
      />
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
                <p className="text-sm mb-2" style={{ color: 'var(--chip-text)' }}>
                  {item.creator}
                </p>
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
              <p className="text-xs uppercase tracking-widest mb-3" style={{ color: 'var(--text2-dark)' }}>
                Thoughts
              </p>
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
              <p className="text-xs uppercase tracking-widest mb-2" style={{ color: 'var(--text2-dark)' }}>
                Thoughts
              </p>
              <p className="text-sm leading-relaxed" style={{ color: 'var(--text-on-dark)' }}>
                {item.summary}
              </p>
            </div>
          )}

          {item.vibe_tags && item.vibe_tags.length > 0 && (
            <div className="mb-5">
              <p className="text-xs uppercase tracking-widest mb-2" style={{ color: 'var(--text2-dark)' }}>
                Vibes
              </p>
              <div className="flex flex-wrap gap-2">
                {item.vibe_tags.map((tag) => (
                  <span
                    key={tag}
                    className="text-xs px-2 py-1 rounded-lg"
                    style={{ background: 'var(--surface2)', color: 'var(--chip-text)' }}
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}

          {item.genres && item.genres.length > 0 && (
            <div className="mb-5">
              <p className="text-xs uppercase tracking-widest mb-2" style={{ color: 'var(--text2-dark)' }}>
                Genres
              </p>
              <div className="flex flex-wrap gap-2">
                {item.genres.map((g) => (
                  <span
                    key={g}
                    className="text-xs px-2 py-1 rounded-lg"
                    style={{ background: 'var(--surface2)', color: 'var(--chip-text)' }}
                  >
                    {g}
                  </span>
                ))}
              </div>
            </div>
          )}

          {item.description && (
            <div className="mb-5">
              <p className="text-xs uppercase tracking-widest mb-2" style={{ color: 'var(--text2-dark)' }}>
                About
              </p>
              <p className="text-sm leading-relaxed" style={{ color: 'var(--chip-text)' }}>
                {item.description}
              </p>
            </div>
          )}

          <div className="h-6" />
        </div>
      </div>
    </>
  )
}

export default function Home() {
  const [tab, setTab] = useState<'library' | 'want'>('library')
  const [typeFilter, setTypeFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [feelingFilter, setFeelingFilter] = useState<string>('all')
  const [items, setItems] = useState<Item[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<Item | null>(null)

  useEffect(() => {
    async function load() {
      setLoading(true)

      let statuses: string[]
      if (tab === 'want') {
        statuses = ['want']
      } else if (statusFilter !== 'all') {
        statuses = [statusFilter]
      } else {
        statuses = ['done', 'in_progress', 'abandoned']
      }

      let query = supabase
        .from('items')
        .select('*')
        .in('status', statuses)
        .order('added_at', { ascending: false })

      if (typeFilter !== 'all') {
        query = query.eq('type', typeFilter)
      }

      if (tab === 'library' && feelingFilter !== 'all') {
        query = query.eq('feeling', feelingFilter)
      }

      const { data } = await query
      setItems(data || [])
      setLoading(false)
    }
    load()
  }, [tab, typeFilter, statusFilter, feelingFilter])

  const showSections = tab === 'library' && statusFilter === 'all'
  const inProgress = items.filter((i) => i.status === 'in_progress')
  const finished = items.filter((i) => i.status === 'done' || i.status === 'abandoned')

  function FilterPill({
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
        className="flex-shrink-0 text-xs font-medium px-3 py-1.5 rounded-full transition-colors"
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

  return (
    <div className="min-h-screen pb-24" style={{ background: 'var(--bg)' }}>
      {/* Header */}
      <header className="px-5 pt-12 pb-4">
        <h1
          style={{
            fontFamily: "'DM Serif Display', serif",
            fontSize: '2rem',
            color: 'var(--text)',
            lineHeight: 1.1,
          }}
        >
          Content Palace
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--text2)' }}>
          Your personal library
        </p>
      </header>

      {/* Tabs */}
      <div className="px-5 flex gap-0" style={{ borderBottom: '1px solid var(--border)' }}>
        {(['library', 'want'] as const).map((t) => (
          <button
            key={t}
            onClick={() => { setTab(t); setStatusFilter('all'); setFeelingFilter('all') }}
            className="px-4 py-2.5 text-sm font-medium relative"
            style={{ color: tab === t ? 'var(--text)' : 'var(--text2)' }}
          >
            {t === 'library' ? 'Library' : 'Want List'}
            {tab === t && (
              <span
                className="absolute bottom-0 left-0 right-0 h-0.5 rounded-t"
                style={{ background: 'var(--accent)' }}
              />
            )}
          </button>
        ))}
      </div>

      {/* Type filters */}
      <div className="px-5 pt-3 pb-2 flex gap-2 overflow-x-auto">
        <FilterPill active={typeFilter === 'all'} onClick={() => setTypeFilter('all')}>
          All
        </FilterPill>
        {TYPES.filter((t) => t !== 'all').map((t) => (
          <FilterPill key={t} active={typeFilter === t} onClick={() => setTypeFilter(t)}>
            {TYPE_ICON[t]} {t}s
          </FilterPill>
        ))}
      </div>

      {/* Status filters (library only) */}
      {tab === 'library' && (
        <div className="px-5 pb-2 flex gap-2 overflow-x-auto">
          {STATUS_FILTERS.map((s) => (
            <FilterPill key={s} active={statusFilter === s} onClick={() => setStatusFilter(s)}>
              {STATUS_LABEL[s]}
            </FilterPill>
          ))}
        </div>
      )}

      {/* Rating filters (library only) */}
      {tab === 'library' && (
        <div className="px-5 pb-3 flex gap-2 overflow-x-auto">
          <FilterPill active={feelingFilter === 'all'} onClick={() => setFeelingFilter('all')}>
            All
          </FilterPill>
          {FEELING_FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFeelingFilter(f)}
              className="flex-shrink-0 text-base px-2.5 py-1 rounded-full transition-colors"
              style={{
                background: feelingFilter === f ? 'var(--accent-dim)' : 'transparent',
                border: `1px solid ${feelingFilter === f ? 'var(--accent)' : 'var(--border)'}`,
              }}
            >
              {FEELING_EMOJI[f]}
            </button>
          ))}
        </div>
      )}

      {/* Content */}
      <div className="px-4 pt-2">
        {loading ? (
          <div className="flex justify-center py-24">
            <div
              className="w-6 h-6 rounded-full border-2 animate-spin"
              style={{ borderColor: 'var(--border)', borderTopColor: 'var(--accent)' }}
            />
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <p className="text-4xl mb-4">📚</p>
            <p style={{ color: 'var(--text2)' }}>
              {tab === 'want' ? 'Your want list is empty' : 'Nothing here yet'}
            </p>
            <p className="text-sm mt-1" style={{ color: 'var(--text2)' }}>
              Add something via Telegram
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {showSections && inProgress.length > 0 && (
              <section>
                <p className="text-xs uppercase tracking-widest mb-3" style={{ color: 'var(--text2)' }}>
                  Currently
                </p>
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
                  <p className="text-xs uppercase tracking-widest mb-3" style={{ color: 'var(--text2)' }}>
                    Finished
                  </p>
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

      {selected && <ItemDrawer item={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
