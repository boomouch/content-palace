'use client'

import { useEffect, useState } from 'react'
import { supabase, Item } from '@/lib/supabase'

const FEELING_LABEL: Record<string, string> = {
  essential: 'Essential',
  loved: 'Loved it',
  good: 'Really good',
  fine: 'Fine',
  not_for_me: 'Not for me',
  regret: 'Regret it',
}

const TYPE_ICON: Record<string, string> = {
  book: '📖',
  film: '🎬',
  show: '📺',
  other: '◆',
}

const TYPES = ['all', 'book', 'film', 'show', 'other'] as const

function ItemCard({ item, onClick }: { item: Item; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left rounded-xl overflow-hidden transition-transform active:scale-[0.97]"
      style={{ background: 'var(--surface)', border: '1px solid var(--border-dark)' }}
    >
      {/* Cover */}
      <div className="w-full overflow-hidden" style={{ aspectRatio: '2/3' }}>
        {item.cover_url ? (
          <img
            src={item.cover_url}
            alt={item.title}
            className="w-full h-full object-cover"
          />
        ) : (
          <div
            className="w-full h-full flex items-center justify-center text-3xl"
            style={{ background: 'var(--surface2)' }}
          >
            {TYPE_ICON[item.type] || '◆'}
          </div>
        )}
      </div>

      {/* Info */}
      <div className="p-3">
        <p className="text-xs mb-1" style={{ color: 'var(--text2-dark)' }}>
          {TYPE_ICON[item.type]}
        </p>
        <h3
          className="font-semibold text-sm leading-snug mb-1 line-clamp-2"
          style={{ color: 'var(--text-on-dark)' }}
        >
          {item.title}
        </h3>
        {item.creator && (
          <p className="text-xs mb-2 truncate" style={{ color: 'var(--text2-dark)' }}>
            {item.creator}{item.year ? ` · ${item.year}` : ''}
          </p>
        )}
        {item.feeling && (
          <span
            className="inline-block text-xs px-2 py-0.5 rounded-full"
            style={{ background: 'rgba(201,146,42,0.15)', color: 'var(--accent)' }}
          >
            {FEELING_LABEL[item.feeling]}
          </span>
        )}
        {item.vibe_tags && item.vibe_tags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {item.vibe_tags.slice(0, 2).map((tag) => (
              <span
                key={tag}
                className="text-xs px-1.5 py-0.5 rounded"
                style={{ background: 'var(--border-dark)', color: 'var(--text2-dark)' }}
              >
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>
    </button>
  )
}

function ItemDrawer({ item, onClose }: { item: Item; onClose: () => void }) {
  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = ''
    }
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
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40"
        style={{ background: 'rgba(0,0,0,0.65)' }}
        onClick={onClose}
      />

      {/* Sheet */}
      <div
        className="fixed bottom-0 left-0 right-0 z-50 rounded-t-2xl overflow-y-auto"
        style={{ background: 'var(--surface)', maxHeight: '88vh' }}
      >
        <div className="p-5">
          {/* Drag handle */}
          <div
            className="w-10 h-1 rounded-full mx-auto mb-5"
            style={{ background: 'var(--border-dark)' }}
          />

          {/* Header row */}
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
                style={{
                  color: 'var(--text-on-dark)',
                  fontFamily: "'DM Serif Display', serif",
                }}
              >
                {item.title}
              </h2>
              {item.creator && (
                <p className="text-sm" style={{ color: 'var(--text2-dark)' }}>
                  {item.creator}
                </p>
              )}
              <div className="flex flex-wrap gap-2 mt-2">
                {item.feeling && (
                  <span
                    className="text-xs px-2 py-0.5 rounded-full"
                    style={{ background: 'rgba(201,146,42,0.15)', color: 'var(--accent)' }}
                  >
                    {FEELING_LABEL[item.feeling]}
                  </span>
                )}
                {item.would_revisit && (
                  <span
                    className="text-xs px-2 py-0.5 rounded-full"
                    style={{ background: 'var(--surface2)', color: 'var(--text2-dark)' }}
                  >
                    {item.would_revisit === 'yes'
                      ? '↩ Would revisit'
                      : item.would_revisit === 'maybe'
                      ? '↩ Maybe revisit'
                      : '— Probably not'}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Quote */}
          {item.highlight_quote && (
            <blockquote
              className="mb-5 pl-3 italic text-sm leading-relaxed"
              style={{
                borderLeft: '2px solid var(--accent)',
                color: 'var(--text-on-dark)',
              }}
            >
              &ldquo;{item.highlight_quote}&rdquo;
            </blockquote>
          )}

          {/* Highlights */}
          {highlights.length > 0 && (
            <div className="mb-5">
              <p
                className="text-xs uppercase tracking-widest mb-3"
                style={{ color: 'var(--text2-dark)' }}
              >
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

          {/* Plain summary fallback */}
          {!highlights.length && item.summary && (
            <div className="mb-5">
              <p
                className="text-xs uppercase tracking-widest mb-2"
                style={{ color: 'var(--text2-dark)' }}
              >
                Thoughts
              </p>
              <p className="text-sm leading-relaxed" style={{ color: 'var(--text-on-dark)' }}>
                {item.summary}
              </p>
            </div>
          )}

          {/* Vibe tags */}
          {item.vibe_tags && item.vibe_tags.length > 0 && (
            <div className="mb-5">
              <p
                className="text-xs uppercase tracking-widest mb-2"
                style={{ color: 'var(--text2-dark)' }}
              >
                Vibes
              </p>
              <div className="flex flex-wrap gap-2">
                {item.vibe_tags.map((tag) => (
                  <span
                    key={tag}
                    className="text-xs px-2 py-1 rounded-lg"
                    style={{ background: 'var(--surface2)', color: 'var(--text2-dark)' }}
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Genres */}
          {item.genres && item.genres.length > 0 && (
            <div className="mb-5">
              <p
                className="text-xs uppercase tracking-widest mb-2"
                style={{ color: 'var(--text2-dark)' }}
              >
                Genres
              </p>
              <div className="flex flex-wrap gap-2">
                {item.genres.map((g) => (
                  <span
                    key={g}
                    className="text-xs px-2 py-1 rounded-lg"
                    style={{ background: 'var(--surface2)', color: 'var(--text2-dark)' }}
                  >
                    {g}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Description */}
          {item.description && (
            <div className="mb-5">
              <p
                className="text-xs uppercase tracking-widest mb-2"
                style={{ color: 'var(--text2-dark)' }}
              >
                About
              </p>
              <p className="text-sm leading-relaxed" style={{ color: 'var(--text2-dark)' }}>
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
  const [items, setItems] = useState<Item[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<Item | null>(null)

  useEffect(() => {
    async function load() {
      setLoading(true)
      const statuses =
        tab === 'want' ? ['want'] : ['done', 'in_progress', 'abandoned']

      let query = supabase
        .from('items')
        .select('*')
        .in('status', statuses)
        .order('added_at', { ascending: false })

      if (typeFilter !== 'all') {
        query = query.eq('type', typeFilter)
      }

      const { data } = await query
      setItems(data || [])
      setLoading(false)
    }
    load()
  }, [tab, typeFilter])

  const inProgress = items.filter((i) => i.status === 'in_progress')
  const finished = items.filter((i) => i.status === 'done' || i.status === 'abandoned')

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
      <div
        className="px-5 flex gap-0"
        style={{ borderBottom: '1px solid var(--border)' }}
      >
        {(['library', 'want'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
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
      <div className="px-5 pt-4 pb-2 flex gap-2 overflow-x-auto">
        {TYPES.map((t) => (
          <button
            key={t}
            onClick={() => setTypeFilter(t)}
            className="flex-shrink-0 text-xs font-medium px-3 py-1.5 rounded-full transition-colors capitalize"
            style={{
              background: typeFilter === t ? 'var(--surface)' : 'transparent',
              color: typeFilter === t ? 'var(--text-on-dark)' : 'var(--text2)',
              border: `1px solid ${typeFilter === t ? 'var(--surface)' : 'var(--border)'}`,
            }}
          >
            {t === 'all' ? 'All' : `${TYPE_ICON[t]} ${t}s`}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="px-5 pt-4">
        {loading ? (
          <div className="flex justify-center py-24">
            <div
              className="w-6 h-6 rounded-full border-2 animate-spin"
              style={{
                borderColor: 'var(--border)',
                borderTopColor: 'var(--accent)',
              }}
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
          <div className="space-y-8">
            {/* Currently reading/watching */}
            {tab === 'library' && inProgress.length > 0 && (
              <section>
                <p
                  className="text-xs uppercase tracking-widest mb-3"
                  style={{ color: 'var(--text2)' }}
                >
                  Currently
                </p>
                <div className="grid grid-cols-2 gap-3">
                  {inProgress.map((item) => (
                    <ItemCard
                      key={item.id}
                      item={item}
                      onClick={() => setSelected(item)}
                    />
                  ))}
                </div>
              </section>
            )}

            {/* Finished */}
            {tab === 'library' && finished.length > 0 && (
              <section>
                {inProgress.length > 0 && (
                  <p
                    className="text-xs uppercase tracking-widest mb-3"
                    style={{ color: 'var(--text2)' }}
                  >
                    Finished
                  </p>
                )}
                <div className="grid grid-cols-2 gap-3">
                  {finished.map((item) => (
                    <ItemCard
                      key={item.id}
                      item={item}
                      onClick={() => setSelected(item)}
                    />
                  ))}
                </div>
              </section>
            )}

            {/* Want list */}
            {tab === 'want' && (
              <div className="grid grid-cols-2 gap-3">
                {items.map((item) => (
                  <ItemCard
                    key={item.id}
                    item={item}
                    onClick={() => setSelected(item)}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {selected && (
        <ItemDrawer item={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}
