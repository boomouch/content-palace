'use client'

import { useEffect, useRef, useState } from 'react'
import { supabase, Item, Recommendation, User } from '@/lib/supabase'

// ── i18n ──
const T = {
  en: {
    nav_library: 'LIBRARY', nav_want: 'WANT', nav_discover: 'DISCOVER', nav_profile: 'PROFILE',
    title_library: 'LIBRARY', title_want: 'WANT LIST', title_discover: 'DISCOVER', title_profile: 'PROFILE',
    sub_library: 'Your personal library', sub_want: 'Things to read & watch',
    sub_discover: 'Picks based on your taste', sub_profile: 'Your taste in numbers',
    currently: 'Currently', finished_section: 'Finished',
    filter_all: 'ALL', filter_books: 'BOOKS', filter_films: 'FILMS', filter_shows: 'SHOWS', filter_others: 'OTHERS',
    filter_current: 'CURRENT', filter_done: 'FINISHED', filter_abandoned: 'DROPPED',
    empty_library: 'Nothing here yet', empty_want: 'Nothing saved yet', empty_add: 'Add something via Telegram',
    drawer_thoughts: 'Thoughts', drawer_vibes: 'Vibes', drawer_genres: 'Genres', drawer_about: 'About',
    drawer_started: 'Started', drawer_finished: 'Finished', drawer_abandoned: 'Abandoned',
    featured_current: 'CURRENT', show_all: 'Show all', show_less: 'Show less',
    profile_empty: 'Your palace is empty', profile_empty_sub: 'Add something via Telegram to see your profile',
    profile_rate_hint: 'Rate at least 3 items via Telegram to unlock your taste profile.',
    profile_update: 'Update', profile_updating: 'Updating...',
    thinking: 'Thinking...', type_book: 'Books', type_film: 'Films', type_show: 'Shows', type_other: 'Others',
    profile_your_taste: 'Your taste', profile_ratings: 'Ratings', profile_fav_genres: 'Favourite genres',
    profile_your_vibes: 'Your vibes', profile_creators: 'Creators you keep coming back to',
    discover_films: '🎬 Films', discover_shows: '📺 Shows', discover_books: '📖 Books',
    discover_my_vibe: '🎯 My Vibe', discover_out_of_lane: '🎲 Out of My Lane',
    discover_easy: '🛋️ Easy Watch/Read', discover_demanding: '🧠 Demanding',
    discover_new: 'New', discover_find: 'Find for me', discover_refresh: 'Refresh picks',
    discover_finding: 'Finding...', discover_picking: 'Picking something for you...',
    discover_empty: 'Nothing yet', discover_empty_sub: 'Set your filters and tap Find for me',
    rec_want: '+ Want list', rec_on_want: 'On want list ✓',
    dismiss_why: 'Why not', dismiss_remove: 'Remove',
    dismiss_seen: 'Seen it', dismiss_not_my_thing: 'Not my thing', dismiss_wrong_vibe: 'Wrong vibe', dismiss_not_mood: 'Not in the mood',
  },
  ru: {
    nav_library: 'КОЛЛЕКЦИЯ', nav_want: 'СОХРАНЁННЫЕ', nav_discover: 'ЧТО СМОТРЕТЬ?', nav_profile: 'ПРОФИЛЬ',
    title_library: 'КОЛЛЕКЦИЯ', title_want: 'СОХРАНЁННЫЕ', title_discover: 'ЧТО СМОТРЕТЬ?', title_profile: 'ПРОФИЛЬ',
    sub_library: 'Личная коллекция', sub_want: 'Список желаний',
    sub_discover: 'Подборка под твой вкус', sub_profile: 'Твой вкус в цифрах',
    currently: 'Сейчас читаю / смотрю', finished_section: 'Завершено',
    filter_all: 'ВСЁ', filter_books: 'КНИГИ', filter_films: 'ФИЛЬМЫ', filter_shows: 'СЕРИАЛЫ', filter_others: 'ПРОЧЕЕ',
    filter_current: 'В ПРОЦЕССЕ', filter_done: 'ЗАВЕРШЕНО', filter_abandoned: 'БРОШЕНО',
    empty_library: 'Пока пусто', empty_want: 'Список пуст', empty_add: 'Добавляй через Telegram',
    drawer_thoughts: 'Мысли', drawer_vibes: 'Ощущения', drawer_genres: 'Жанры', drawer_about: 'О чём',
    drawer_started: 'Начато', drawer_finished: 'Завершено', drawer_abandoned: 'Брошено',
    featured_current: 'СЕЙЧАС', show_all: 'Показать все', show_less: 'Свернуть',
    profile_empty: 'Дворец пустой', profile_empty_sub: 'Добавь что-нибудь через Telegram',
    profile_rate_hint: 'Оцени хотя бы 3 записи через Telegram чтобы открыть вкусовой профиль.',
    profile_update: 'Обновить', profile_updating: 'Обновляю...',
    thinking: 'Думаю...', type_book: 'Книги', type_film: 'Фильмы', type_show: 'Сериалы', type_other: 'Прочее',
    profile_your_taste: 'Твой вкус', profile_ratings: 'Оценки', profile_fav_genres: 'Любимые жанры',
    profile_your_vibes: 'Твои вайбы', profile_creators: 'Авторы, к которым возвращаешься',
    discover_films: '🎬 Фильмы', discover_shows: '📺 Сериалы', discover_books: '📖 Книги',
    discover_my_vibe: '🎯 Мой вайб', discover_out_of_lane: '🎲 Что-то новое',
    discover_easy: '🛋️ Лёгкое', discover_demanding: '🧠 Серьёзное',
    discover_new: 'Новинки', discover_find: 'Найти', discover_refresh: 'Обновить',
    discover_finding: 'Ищу...', discover_picking: 'Подбираю для тебя...',
    discover_empty: 'Пока ничего', discover_empty_sub: 'Выбери фильтры и нажми Найти',
    rec_want: '+ В список', rec_on_want: 'В списке ✓',
    dismiss_why: 'Почему не', dismiss_remove: 'Убрать',
    dismiss_seen: 'Уже видел(а)', dismiss_not_my_thing: 'Не моё', dismiss_wrong_vibe: 'Не тот вайб', dismiss_not_mood: 'Не в настроении',
  },
} as const
type TKey = keyof typeof T['en']

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

function IconCompass({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="10" cy="10" r="7.5"/>
      <polygon points="13,7 11.5,12.5 7,13 8.5,7.5" fill="currentColor" stroke="none" opacity="0.4"/>
      <path d="M13 7l-4.5 5.5M8.5 7.5L11.5 12.5"/>
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
function FeaturedCard({ item, onClick, lang }: { item: Item; onClick: () => void; lang: 'en' | 'ru' }) {
  const tx = T[lang]
  const displayTitle = lang === 'ru' && item.title_ru ? item.title_ru : item.title
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
            {displayTitle}
          </h3>
          {item.creator && (
            <p className="text-sm mb-3" style={{ color: 'var(--text2)' }}>{item.creator}</p>
          )}
          <span
            className="inline-flex items-center text-xs font-bold tracking-wider px-2.5 py-1 rounded-full"
            style={{ background: 'var(--text)', color: 'var(--bg)' }}
          >
            {tx.featured_current}
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
function ItemCard({ item, onClick, lang }: { item: Item; onClick: () => void; lang: 'en' | 'ru' }) {
  const emoji = item.feeling ? FEELING_EMOJI[item.feeling] : null
  const displayTitle = lang === 'ru' && item.title_ru ? item.title_ru : item.title
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
          {displayTitle}
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
function ItemDrawer({ item, onClose, lang }: { item: Item; onClose: () => void; lang: 'en' | 'ru' }) {
  const tx = T[lang]
  const displayTitle = lang === 'ru' && item.title_ru ? item.title_ru : item.title
  const displayDescription = lang === 'ru' && item.description_ru ? item.description_ru : item.description
  const [dragY, setDragY] = useState(0)
  const [dragging, setDragging] = useState(false)
  const startYRef = useRef(0)
  const drawerRef = useRef<HTMLDivElement>(null)
  const closedByBackRef = useRef(false)

  useEffect(() => {
    document.body.style.overflow = 'hidden'
    window.history.pushState({ drawer: true }, '')
    const handlePop = () => {
      closedByBackRef.current = true
      onClose()
    }
    window.addEventListener('popstate', handlePop)
    return () => {
      document.body.style.overflow = ''
      window.removeEventListener('popstate', handlePop)
      if (!closedByBackRef.current) window.history.back()
    }
  }, [])

  function onTouchStart(e: React.TouchEvent) {
    startYRef.current = e.touches[0].clientY
    setDragging(true)
  }

  function onTouchMove(e: React.TouchEvent) {
    if (!dragging) return
    const delta = e.touches[0].clientY - startYRef.current
    if (delta > 0 && (drawerRef.current?.scrollTop ?? 0) === 0) setDragY(delta)
  }

  function onTouchEnd() {
    setDragging(false)
    if (dragY > 100) onClose()
    else setDragY(0)
  }

  const highlights: string[] = (() => {
    if (lang === 'ru' && item.highlights_ru?.length) return item.highlights_ru
    if (!item.summary) return []
    try {
      const parsed = JSON.parse(item.summary)
      if (Array.isArray(parsed)) return parsed
    } catch {}
    return []
  })()
  const plainSummary = lang === 'ru' && item.summary_ru ? item.summary_ru : (item.summary && !item.summary.startsWith('[') ? item.summary : null)
  const vibeTags = (lang === 'ru' && item.vibe_tags_ru?.length ? item.vibe_tags_ru : item.vibe_tags) || []
  const genres = (lang === 'ru' && item.genres_ru?.length ? item.genres_ru : item.genres) || []

  return (
    <>
      <div className="fixed inset-0 z-40" style={{ background: 'rgba(0,0,0,0.35)' }} onClick={onClose} />
      <div
        ref={drawerRef}
        className="fixed bottom-0 left-0 right-0 z-50 rounded-t-2xl overflow-y-auto"
        style={{
          background: 'var(--card-bg)',
          maxHeight: '88vh',
          transform: `translateY(${dragY}px)`,
          transition: dragging ? 'none' : 'transform 0.25s ease',
        }}
        onTouchStart={onTouchStart}
        onTouchMove={onTouchMove}
        onTouchEnd={onTouchEnd}
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
                {displayTitle}
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
                      {tx.drawer_started} {new Date(item.started_at).toLocaleDateString(lang === 'ru' ? 'ru-RU' : 'en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
                    </span>
                  )}
                  {item.finished_at && (
                    <span className="text-xs" style={{ color: 'var(--text2)' }}>
                      {item.status === 'abandoned' ? tx.drawer_abandoned : tx.drawer_finished} {new Date(item.finished_at).toLocaleDateString(lang === 'ru' ? 'ru-RU' : 'en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
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
              <p className="text-xs uppercase tracking-widest mb-3" style={{ color: 'var(--text2)' }}>{tx.drawer_thoughts}</p>
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

          {!highlights.length && plainSummary && (
            <div className="mb-5">
              <p className="text-xs uppercase tracking-widest mb-2" style={{ color: 'var(--text2)' }}>{tx.drawer_thoughts}</p>
              <p className="text-sm leading-relaxed" style={{ color: 'var(--text)' }}>{plainSummary}</p>
            </div>
          )}

          {vibeTags.length > 0 && (
            <div className="mb-5">
              <p className="text-xs uppercase tracking-widest mb-2" style={{ color: 'var(--text2)' }}>{tx.drawer_vibes}</p>
              <div className="flex flex-wrap gap-2">
                {vibeTags.map((tag) => (
                  <span key={tag} className="text-xs px-2.5 py-1 rounded-lg" style={{ background: 'var(--card-bg2)', color: 'var(--chip-text)', border: '1px solid var(--border)' }}>{tag}</span>
                ))}
              </div>
            </div>
          )}

          {genres.length > 0 && (
            <div className="mb-5">
              <p className="text-xs uppercase tracking-widest mb-2" style={{ color: 'var(--text2)' }}>{tx.drawer_genres}</p>
              <div className="flex flex-wrap gap-2">
                {genres.map((g) => (
                  <span key={g} className="text-xs px-2.5 py-1 rounded-lg capitalize" style={{ background: 'var(--card-bg2)', color: 'var(--chip-text)', border: '1px solid var(--border)' }}>{g}</span>
                ))}
              </div>
            </div>
          )}

          {displayDescription && (
            <div className="mb-5">
              <p className="text-xs uppercase tracking-widest mb-2" style={{ color: 'var(--text2)' }}>{tx.drawer_about}</p>
              <p className="text-sm leading-relaxed" style={{ color: 'var(--text2)' }}>{displayDescription}</p>
            </div>
          )}

          <div className="h-6" />
        </div>
      </div>
    </>
  )
}

// ── Discover tab ──
type DiscoverFilters = {
  type: 'film' | 'show' | 'book' | null
  style: 'my_vibe' | 'out_of_lane' | null
  intensity: 'easy' | 'demanding' | null
  new_only: boolean
}

function RecommendationCard({
  rec,
  onDismiss,
  onWant,
  lang,
}: {
  rec: Recommendation
  onDismiss: (rec: Recommendation) => void
  onWant: (rec: Recommendation) => void
  lang: 'en' | 'ru'
}) {
  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', boxShadow: 'var(--card-shadow)' }}
    >
      <div className="flex">
        <div style={{ width: '36%', flexShrink: 0 }}>
          <div className="w-full" style={{ minHeight: '160px', height: '100%' }}>
            {rec.cover_url ? (
              <img src={rec.cover_url} alt={rec.title} className="w-full h-full object-cover" style={{ minHeight: '160px' }} />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-3xl" style={{ background: 'var(--card-bg2)', minHeight: '160px' }}>
                {rec.type === 'book' ? '📖' : rec.type === 'show' ? '📺' : '🎬'}
              </div>
            )}
          </div>
        </div>
        <div className="flex-1 p-4 flex flex-col justify-between min-w-0">
          <div>
            {rec.year && (
              <p className="text-xs mb-1 tabular-nums" style={{ color: 'var(--text2)' }}>{rec.year}</p>
            )}
            <h3
              className="font-bold leading-tight mb-1"
              style={{ fontFamily: "'DM Serif Display', serif", fontSize: '1.15rem', color: 'var(--text)' }}
            >
              {lang === 'ru' && rec.title_ru ? rec.title_ru : rec.title}
            </h3>
            {rec.creator && (
              <p className="text-sm" style={{ color: 'var(--text2)' }}>{rec.creator}</p>
            )}
          </div>
          <div className="flex gap-2 mt-3">
            {rec.added_to_want ? (
              <span
                className="flex-1 text-center text-xs font-medium py-2 rounded-xl"
                style={{ background: 'var(--accent-dim)', color: 'var(--accent)' }}
              >
                {T[lang].rec_on_want}
              </span>
            ) : (
              <button
                onClick={() => onWant(rec)}
                className="flex-1 text-xs font-medium py-2 rounded-xl"
                style={{ background: 'var(--text)', color: 'var(--bg)' }}
              >
                {T[lang].rec_want}
              </button>
            )}
            <button
              onClick={() => onDismiss(rec)}
              className="px-3 py-2 rounded-xl text-sm"
              style={{ background: 'var(--card-bg2)', border: '1px solid var(--border)', color: 'var(--text2)' }}
              title="Not interested"
            >
              👎
            </button>
          </div>
        </div>
      </div>
      <div className="px-4 pb-4 pt-1">
        <p className="leading-relaxed italic" style={{ color: 'var(--text)', fontFamily: "'DM Serif Display', serif", fontSize: '0.95rem', textAlign: 'justify' }}>
          {lang === 'ru' && rec.why_ru ? rec.why_ru : rec.why}
        </p>
      </div>
    </div>
  )
}

function DismissSheet({
  rec,
  onConfirm,
  onCancel,
  lang,
}: {
  rec: Recommendation
  onConfirm: (reason: string | null) => void
  onCancel: () => void
  lang: 'en' | 'ru'
}) {
  const [selected, setSelected] = useState<string | null>(null)
  const tx = T[lang]
  const dismissReasons = [tx.dismiss_seen, tx.dismiss_not_my_thing, tx.dismiss_wrong_vibe, tx.dismiss_not_mood]

  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [])

  return (
    <>
      <div className="fixed inset-0 z-40" style={{ background: 'rgba(0,0,0,0.35)' }} onClick={onCancel} />
      <div
        className="fixed bottom-0 left-0 right-0 z-50 rounded-t-2xl p-5"
        style={{ background: 'var(--card-bg)' }}
      >
        <div className="w-8 h-1 rounded-full mx-auto mb-5" style={{ background: 'var(--border)' }} />
        <p className="text-sm font-medium mb-4" style={{ color: 'var(--text2)' }}>
          {tx.dismiss_why} <span style={{ color: 'var(--text)' }}>{rec.title}</span>?
        </p>
        <div className="flex flex-wrap gap-2 mb-5">
          {dismissReasons.map((r) => (
            <button
              key={r}
              onClick={() => setSelected(selected === r ? null : r)}
              className="text-sm px-4 py-2 rounded-full"
              style={{
                background: selected === r ? 'var(--text)' : 'transparent',
                color: selected === r ? 'var(--bg)' : 'var(--text2)',
                border: `1px solid ${selected === r ? 'var(--text)' : 'var(--border)'}`,
              }}
            >
              {r}
            </button>
          ))}
        </div>
        <button
          onClick={() => onConfirm(selected)}
          className="w-full py-3 rounded-xl text-sm font-medium"
          style={{ background: 'var(--text)', color: 'var(--bg)' }}
        >
          {tx.dismiss_remove}
        </button>
      </div>
    </>
  )
}

function DiscoverPage({ lang, telegramId }: { lang: 'en' | 'ru', telegramId: number | null }) {
  const tx = T[lang]
  const [filters, setFilters] = useState<DiscoverFilters>({
    type: null,
    style: null,
    intensity: null,
    new_only: false,
  })
  const [recs, setRecs] = useState<Recommendation[]>([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [dismissTarget, setDismissTarget] = useState<Recommendation | null>(null)

  useEffect(() => {
    const url = telegramId ? `/api/recommendations?telegram_id=${telegramId}` : '/api/recommendations'
    fetch(url)
      .then((r) => r.json())
      .then((data) => setRecs(Array.isArray(data) ? data : []))
      .finally(() => setLoading(false))
  }, [telegramId])

  async function generate() {
    setGenerating(true)
    try {
      const res = await fetch('/api/recommendations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filters, telegram_id: telegramId }),
      })
      const data = await res.json()
      setRecs(Array.isArray(data) ? data : [])
    } finally {
      setGenerating(false)
    }
  }

  async function handleDismiss(rec: Recommendation, reason: string | null) {
    setDismissTarget(null)
    setRecs((prev) => prev.filter((r) => r.id !== rec.id))
    await fetch(`/api/recommendations/${rec.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'dismiss', reason }),
    })
  }

  async function handleWant(rec: Recommendation) {
    setRecs((prev) => prev.map((r) => (r.id === rec.id ? { ...r, added_to_want: true } : r)))
    await fetch(`/api/recommendations/${rec.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'want', item: rec }),
    })
  }

  function toggleStyle(val: 'my_vibe' | 'out_of_lane') {
    setFilters((f) => ({ ...f, style: f.style === val ? null : val }))
  }

  function toggleIntensity(val: 'easy' | 'demanding') {
    setFilters((f) => ({ ...f, intensity: f.intensity === val ? null : val }))
  }

  function toggleType(val: 'film' | 'show' | 'book') {
    setFilters((f) => ({ ...f, type: f.type === val ? null : val }))
  }

  return (
    <div className="px-4 pt-5 pb-6">
      {/* Filters */}
      <div className="space-y-3 mb-5">
        {/* Type */}
        <div className="flex gap-2">
          {(['film', 'show', 'book'] as const).map((t) => (
            <button
              key={t}
              onClick={() => toggleType(t)}
              className="flex-1 py-2 text-xs font-medium rounded-xl capitalize"
              style={{
                background: filters.type === t ? 'var(--text)' : 'var(--card-bg)',
                color: filters.type === t ? 'var(--bg)' : 'var(--text2)',
                border: `1px solid ${filters.type === t ? 'var(--text)' : 'var(--border)'}`,
              }}
            >
              {t === 'film' ? tx.discover_films : t === 'show' ? tx.discover_shows : tx.discover_books}
            </button>
          ))}
        </div>

        {/* Style */}
        <div className="flex gap-2">
          {(['my_vibe', 'out_of_lane'] as const).map((s) => (
            <button
              key={s}
              onClick={() => toggleStyle(s)}
              className="flex-1 py-2 text-xs font-medium rounded-xl"
              style={{
                background: filters.style === s ? 'var(--text)' : 'var(--card-bg)',
                color: filters.style === s ? 'var(--bg)' : 'var(--text2)',
                border: `1px solid ${filters.style === s ? 'var(--text)' : 'var(--border)'}`,
              }}
            >
              {s === 'my_vibe' ? tx.discover_my_vibe : tx.discover_out_of_lane}
            </button>
          ))}
        </div>

        {/* Intensity */}
        <div className="flex gap-2">
          {(['easy', 'demanding'] as const).map((i) => (
            <button
              key={i}
              onClick={() => toggleIntensity(i)}
              className="flex-1 py-2 text-xs font-medium rounded-xl"
              style={{
                background: filters.intensity === i ? 'var(--text)' : 'var(--card-bg)',
                color: filters.intensity === i ? 'var(--bg)' : 'var(--text2)',
                border: `1px solid ${filters.intensity === i ? 'var(--text)' : 'var(--border)'}`,
              }}
            >
              {i === 'easy' ? tx.discover_easy : tx.discover_demanding}
            </button>
          ))}
        </div>

        {/* New toggle */}
        <button
          onClick={() => setFilters((f) => ({ ...f, new_only: !f.new_only }))}
          className="flex items-center gap-2 py-2 px-4 rounded-xl text-xs font-medium"
          style={{
            background: filters.new_only ? 'var(--text)' : 'var(--card-bg)',
            color: filters.new_only ? 'var(--bg)' : 'var(--text2)',
            border: `1px solid ${filters.new_only ? 'var(--text)' : 'var(--border)'}`,
          }}
        >
          {tx.discover_new}
          <span
            className="text-xs px-1.5 py-0.5 rounded"
            style={{
              background: filters.new_only ? 'rgba(255,255,255,0.2)' : 'var(--accent-dim)',
              color: filters.new_only ? 'var(--bg)' : 'var(--accent)',
              fontSize: '0.6rem',
              fontWeight: 700,
              letterSpacing: '0.05em',
            }}
          >
            BETA
          </span>
        </button>
      </div>

      {/* Generate button */}
      <button
        onClick={generate}
        disabled={generating}
        className="w-full py-3.5 rounded-2xl text-sm font-bold tracking-wide mb-6"
        style={{
          background: generating ? 'var(--border)' : 'var(--text)',
          color: generating ? 'var(--text2)' : 'var(--bg)',
        }}
      >
        {generating ? tx.discover_finding : recs.length > 0 ? tx.discover_refresh : tx.discover_find}
      </button>

      {/* Results */}
      {loading ? (
        <div className="flex justify-center py-16">
          <div className="w-5 h-5 rounded-full border-2 animate-spin" style={{ borderColor: 'var(--border)', borderTopColor: 'var(--text)' }} />
        </div>
      ) : generating ? (
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <div className="w-5 h-5 rounded-full border-2 animate-spin" style={{ borderColor: 'var(--border)', borderTopColor: 'var(--text)' }} />
          <p className="text-sm" style={{ color: 'var(--text2)' }}>{tx.discover_picking}</p>
        </div>
      ) : recs.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <p className="text-4xl mb-4">🧭</p>
          <p className="font-medium mb-1" style={{ color: 'var(--text)' }}>{tx.discover_empty}</p>
          <p className="text-sm" style={{ color: 'var(--text2)' }}>{tx.discover_empty_sub}</p>
        </div>
      ) : (
        <div className="space-y-4">
          {recs.map((rec) => (
            <RecommendationCard
              key={rec.id}
              rec={rec}
              onDismiss={(r) => setDismissTarget(r)}
              onWant={handleWant}
              lang={lang}
            />
          ))}
        </div>
      )}

      {dismissTarget && (
        <DismissSheet
          rec={dismissTarget}
          onConfirm={(reason) => handleDismiss(dismissTarget, reason)}
          onCancel={() => setDismissTarget(null)}
          lang={lang}
        />
      )}
    </div>
  )
}

// ── Profile tab ──
function ProfilePage({ items, lang }: { items: Item[], lang: 'en' | 'ru' }) {
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
  loved.forEach((item) => {
    const gs = (lang === 'ru' && item.genres_ru?.length ? item.genres_ru : item.genres) || []
    gs.forEach((g) => { genreMap[g] = (genreMap[g] || 0) + 1 })
  })
  const topGenres = Object.entries(genreMap).sort((a, b) => b[1] - a[1]).slice(0, 10).map(([g]) => g)

  const vibeMap: Record<string, number> = {}
  loved.forEach((item) => {
    const vs = (lang === 'ru' && item.vibe_tags_ru?.length ? item.vibe_tags_ru : item.vibe_tags) || []
    vs.forEach((t) => { vibeMap[t] = (vibeMap[t] || 0) + 1 })
  })
  const topVibes = Object.entries(vibeMap).sort((a, b) => b[1] - a[1]).slice(0, 12).map(([t]) => t)

  const creatorMap: Record<string, number> = {}
  rated.forEach((item) => { if (item.creator) creatorMap[item.creator] = (creatorMap[item.creator] || 0) + 1 })
  const topCreators = Object.entries(creatorMap).filter(([, c]) => c >= 2).sort((a, b) => b[1] - a[1]).slice(0, 6)

  function generateSummary() {
    if (rated.length < 3 || summaryLoading) return
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
        lang,
      }),
    })
      .then((r) => r.json())
      .then((d) => setTasteSummary(d.summary))
      .finally(() => setSummaryLoading(false))
  }

  const tx = T[lang]
  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-center px-5">
        <p className="text-4xl mb-4">🏰</p>
        <p style={{ color: 'var(--text2)' }}>{tx.profile_empty}</p>
        <p className="text-sm mt-1" style={{ color: 'var(--text2)' }}>{tx.profile_empty_sub}</p>
      </div>
    )
  }

  return (
    <div className="px-4 pt-5 space-y-7 pb-4">

      {/* AI taste summary */}
      <div className="rounded-2xl p-4" style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', boxShadow: 'var(--card-shadow)' }}>
        <div className="flex items-center justify-between mb-3">
          <p className="text-xs uppercase tracking-widest font-bold" style={{ color: 'var(--text2)' }}>{tx.profile_your_taste}</p>
          {rated.length >= 3 && (
            <button
              onClick={generateSummary}
              disabled={summaryLoading}
              className="text-xs px-3 py-1 rounded-full transition-opacity"
              style={{ background: 'var(--accent)', color: 'var(--bg)', opacity: summaryLoading ? 0.5 : 1 }}
            >
              {summaryLoading ? tx.profile_updating : tx.profile_update}
            </button>
          )}
        </div>
        {summaryLoading ? (
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full border-2 animate-spin flex-shrink-0" style={{ borderColor: 'var(--border)', borderTopColor: 'var(--accent)' }} />
            <p className="text-sm" style={{ color: 'var(--text2)' }}>{tx.thinking}</p>
          </div>
        ) : tasteSummary ? (
          <p className="leading-relaxed italic" style={{ color: 'var(--text)', fontFamily: "'DM Serif Display', serif", fontSize: '1.05rem', textAlign: 'justify' }}>
            {tasteSummary}
          </p>
        ) : (
          <p className="text-sm" style={{ color: 'var(--text2)' }}>
            {rated.length >= 3 ? tx.profile_update + ' ↑' : tx.profile_rate_hint}
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
          <p className="text-xs uppercase tracking-widest mb-3 font-bold" style={{ color: 'var(--text2)' }}>{tx.profile_ratings}</p>
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
          <p className="text-xs uppercase tracking-widest mb-3 font-bold" style={{ color: 'var(--text2)' }}>{tx.profile_fav_genres}</p>
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
          <p className="text-xs uppercase tracking-widest mb-3 font-bold" style={{ color: 'var(--text2)' }}>{tx.profile_your_vibes}</p>
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
          <p className="text-xs uppercase tracking-widest mb-3 font-bold" style={{ color: 'var(--text2)' }}>{tx.profile_creators}</p>
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

// ── Profile badge ──
function ProfileBadge({
  users, currentUser, onSwitch,
}: {
  users: User[]; currentUser: User | null; onSwitch: (u: User) => void
}) {
  const [open, setOpen] = useState(false)
  if (!currentUser && users.length === 0) return null
  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-full"
        style={{ background: 'var(--card-bg)', border: '1px solid var(--border)' }}
      >
        <span className="text-sm">{currentUser?.avatar_emoji || '👤'}</span>
        <span className="text-xs font-medium max-w-20 truncate" style={{ color: 'var(--text)' }}>
          {currentUser?.name || '...'}
        </span>
        <span className="text-xs" style={{ color: 'var(--text2)' }}>▾</span>
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div
            className="absolute right-0 top-10 z-50 rounded-2xl overflow-hidden"
            style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', minWidth: '180px', boxShadow: '0 8px 32px rgba(0,0,0,0.15)' }}
          >
            {users.map((u) => (
              <button
                key={u.telegram_id}
                onClick={() => { onSwitch(u); setOpen(false) }}
                className="w-full flex items-center gap-3 px-4 py-3 text-left"
                style={{ background: u.telegram_id === currentUser?.telegram_id ? 'var(--accent-dim)' : 'transparent' }}
              >
                <span>{u.avatar_emoji}</span>
                <span className="text-sm font-medium flex-1" style={{ color: 'var(--text)' }}>{u.name}</span>
                {u.telegram_id === currentUser?.telegram_id && (
                  <span className="text-xs font-bold" style={{ color: 'var(--accent)' }}>✓</span>
                )}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

// ── Per-user pastel palettes ──
const USER_PALETTES = [
  { bg: '#f5f0e8', card2: '#ede8df', border: '#e0d8cc' }, // warm sand (default)
  { bg: '#eef2ec', card2: '#e3ede0', border: '#d4e6cf' }, // sage green
  { bg: '#eeedf5', card2: '#e3e1f0', border: '#d4d1e8' }, // lavender
  { bg: '#f5ecec', card2: '#ede0e0', border: '#e0d0d0' }, // dusty rose
  { bg: '#edf3f8', card2: '#ddeaf3', border: '#cce0ee' }, // sky blue
  { bg: '#f5eeeb', card2: '#ede3de', border: '#e0d4cd' }, // peach
  { bg: '#eaf4f2', card2: '#daeee9', border: '#cae5df' }, // mint
  { bg: '#f2edf0', card2: '#e8dfe4', border: '#dcd0d8' }, // warm mauve
]

function applyUserPalette(telegramId: number) {
  const p = USER_PALETTES[Math.abs(telegramId) % USER_PALETTES.length]
  const root = document.documentElement
  root.style.setProperty('--bg', p.bg)
  root.style.setProperty('--card-bg2', p.card2)
  root.style.setProperty('--border', p.border)
  const r = parseInt(p.bg.slice(1, 3), 16)
  const g = parseInt(p.bg.slice(3, 5), 16)
  const b = parseInt(p.bg.slice(5, 7), 16)
  root.style.setProperty('--nav-bg', `rgba(${r},${g},${b},0.94)`)
  return p
}

// ── Main page ──
export default function Home() {
  const [tab, setTab] = useState<'library' | 'want' | 'discover' | 'profile'>('library')
  const [typeFilters, setTypeFilters] = useState<Set<string>>(new Set())
  const [statusFilters, setStatusFilters] = useState<Set<string>>(new Set())
  const [feelingFilters, setFeelingFilters] = useState<Set<string>>(new Set())
  const [items, setItems] = useState<Item[]>([])
  const [allItems, setAllItems] = useState<Item[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<Item | null>(null)

  // Multi-user + language
  const [lang, setLang] = useState<'en' | 'ru'>('en')
  const [users, setUsers] = useState<User[]>([])
  const [currentUser, setCurrentUser] = useState<User | null>(null)
  const [bgColor, setBgColor] = useState(USER_PALETTES[0].bg)

  // Load persisted lang + user from localStorage (URL param ?user= takes priority)
  useEffect(() => {
    const savedLang = localStorage.getItem('cp_lang') as 'en' | 'ru' | null
    if (savedLang) setLang(savedLang)
    const urlUserId = new URLSearchParams(window.location.search).get('user')
    const savedUserId = localStorage.getItem('cp_user_telegram_id')
    const preferredId = urlUserId || savedUserId
    fetch('/api/users')
      .then((r) => r.json())
      .then((data: User[]) => {
        setUsers(data)
        if (data.length > 0) {
          const match = preferredId ? data.find((u) => String(u.telegram_id) === preferredId) : null
          setCurrentUser(match || data[0])
        }
      })
  }, [])

  // Apply per-user color palette whenever the active user changes
  useEffect(() => {
    if (currentUser) {
      const p = applyUserPalette(currentUser.telegram_id)
      setBgColor(p.bg)
    }
  }, [currentUser])

  function switchUser(u: User) {
    setCurrentUser(u)
    setTab('library')
    localStorage.setItem('cp_user_telegram_id', String(u.telegram_id))
  }

  function toggleLang() {
    const next = lang === 'en' ? 'ru' : 'en'
    setLang(next)
    localStorage.setItem('cp_lang', next)
  }

  const tx = T[lang]

  useEffect(() => {
    if (tab === 'profile' || tab === 'discover') return
    if (!currentUser) { setItems([]); setLoading(false); return }
    async function load() {
      setLoading(true)
      let statuses: string[]
      if (tab === 'want') statuses = ['want']
      else if (statusFilters.size > 0) statuses = [...statusFilters]
      else statuses = ['done', 'in_progress', 'abandoned']

      let query = supabase.from('items').select('*').in('status', statuses).order('added_at', { ascending: false })
      query = query.eq('telegram_id', currentUser!.telegram_id)
      if (typeFilters.size > 0) query = query.in('type', [...typeFilters])
      if (tab === 'library' && feelingFilters.size > 0) query = query.in('feeling', [...feelingFilters])

      const { data } = await query
      setItems(data || [])
      setLoading(false)
    }
    load()
  }, [tab, typeFilters, statusFilters, feelingFilters, currentUser])

  useEffect(() => {
    if (tab !== 'profile') return
    if (!currentUser) { setAllItems([]); setLoading(false); return }
    async function loadAll() {
      setLoading(true)
      const { data } = await supabase.from('items').select('*')
        .in('status', ['done', 'in_progress', 'abandoned'])
        .eq('telegram_id', currentUser!.telegram_id)
        .order('added_at', { ascending: false })
      setAllItems(data || [])
      setLoading(false)
    }
    loadAll()
  }, [tab, currentUser])

  const [showAllFinished, setShowAllFinished] = useState(false)

  const showSections = tab === 'library' && statusFilters.size === 0
  const inProgress = items.filter((i) => i.status === 'in_progress')
  const finished = items.filter((i) => i.status === 'done' || i.status === 'abandoned')
  const FINISHED_LIMIT = 9
  const visibleFinished = showAllFinished ? finished : finished.slice(0, FINISHED_LIMIT)

  function switchTab(t: 'library' | 'want' | 'discover' | 'profile') {
    setTab(t)
    setStatusFilters(new Set())
    setFeelingFilters(new Set())
    setTypeFilters(new Set())
  }

  const PAGE_TITLES: Record<string, string> = {
    library: tx.title_library,
    want: tx.title_want,
    discover: tx.title_discover,
    profile: tx.title_profile,
  }

  const PAGE_SUBTITLES: Record<string, string> = {
    library: tx.sub_library,
    want: tx.sub_want,
    discover: tx.sub_discover,
    profile: tx.sub_profile,
  }

  return (
    <div className="min-h-screen" style={{ background: bgColor, transition: 'background 0.3s ease', paddingBottom: '72px' }}>

      {/* Top bar */}
      <header className="flex items-center justify-between px-5 pt-12 pb-4 gap-3">
        <span className="text-xs font-bold tracking-widest uppercase" style={{ color: 'var(--text)' }}>
          CONTENT PALACE <span style={{ color: 'var(--accent)' }}>•</span>
        </span>
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={toggleLang}
            className="text-xs font-bold px-2.5 py-1.5 rounded-full"
            style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', color: 'var(--text2)' }}
          >
            {lang === 'en' ? 'RU' : 'EN'}
          </button>
          <ProfileBadge users={users} currentUser={currentUser} onSwitch={switchUser} />
        </div>
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
      {tab !== 'profile' && tab !== 'discover' && (
        <div className="pb-3" style={{ borderBottom: '1px solid var(--border)' }}>
          {/* Type filter */}
          <div className="flex gap-2 px-5 pb-2 overflow-x-auto" style={{ scrollbarWidth: 'none' }}>
            <Chip active={typeFilters.size === 0} onClick={() => setTypeFilters(new Set())}>
              <IconGrid size={11} /> {tx.filter_all}
            </Chip>
            {(['book', 'film', 'show', 'other'] as const).map((t) => (
              <Chip key={t} active={typeFilters.has(t)} onClick={() => setTypeFilters(toggleSet(typeFilters, t))}>
                <span className="text-xs">{TYPE_ICON[t]}</span> {t === 'book' ? tx.filter_books : t === 'film' ? tx.filter_films : t === 'show' ? tx.filter_shows : tx.filter_others}
              </Chip>
            ))}
          </div>

          {/* Status + rating filter */}
          {tab === 'library' && (
            <div className="flex gap-2 px-5 overflow-x-auto" style={{ scrollbarWidth: 'none' }}>
              <Chip active={statusFilters.size === 0 && feelingFilters.size === 0} onClick={() => { setStatusFilters(new Set()); setFeelingFilters(new Set()) }}>
                {tx.filter_all}
              </Chip>
              {(['in_progress', 'done', 'abandoned'] as const).map((s) => (
                <Chip key={s} active={statusFilters.has(s)} onClick={() => setStatusFilters(toggleSet(statusFilters, s))}>
                  {s === 'in_progress' ? tx.filter_current : s === 'done' ? tx.filter_done : tx.filter_abandoned}
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
      {tab === 'discover' ? (
        <DiscoverPage lang={(currentUser?.lang ?? 'en') as 'en' | 'ru'} telegramId={currentUser?.telegram_id ?? null} />
      ) : tab === 'profile' ? (
        loading ? (
          <div className="flex justify-center py-24">
            <div className="w-5 h-5 rounded-full border-2 animate-spin" style={{ borderColor: 'var(--border)', borderTopColor: 'var(--text)' }} />
          </div>
        ) : (
          <ProfilePage items={allItems} lang={(currentUser?.lang ?? 'en') as 'en' | 'ru'} />
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
              <p style={{ color: 'var(--text2)' }}>{tab === 'want' ? tx.empty_want : tx.empty_library}</p>
              <p className="text-sm mt-1" style={{ color: 'var(--text2)' }}>{tx.empty_add}</p>
            </div>
          ) : (
            <div className="space-y-6">
              {showSections && inProgress.length > 0 && (
                <section>
                  <SectionHeader title={tx.currently} />
                  <div
                    className="flex gap-3 overflow-x-auto pb-1"
                    style={{ scrollbarWidth: 'none', scrollSnapType: 'x mandatory' }}
                  >
                    {inProgress.map((item) => (
                      <div key={item.id} style={{ minWidth: '82vw', maxWidth: '82vw', scrollSnapAlign: 'start' }}>
                        <FeaturedCard item={item} onClick={() => setSelected(item)} lang={lang} />
                      </div>
                    ))}
                  </div>
                </section>
              )}
              {showSections && finished.length > 0 && (
                <section>
                  <SectionHeader title={tx.finished_section} />
                  <div className="grid grid-cols-3 gap-2.5">
                    {visibleFinished.map((item) => <ItemCard key={item.id} item={item} onClick={() => setSelected(item)} lang={lang} />)}
                  </div>
                  {finished.length > FINISHED_LIMIT && (
                    <button
                      onClick={() => setShowAllFinished(!showAllFinished)}
                      className="w-full mt-3 py-2.5 text-xs font-medium tracking-wide uppercase rounded-xl"
                      style={{ border: '1px solid var(--border)', color: 'var(--text2)' }}
                    >
                      {showAllFinished ? tx.show_less : `${tx.show_all} ${finished.length}`}
                    </button>
                  )}
                </section>
              )}
              {!showSections && (
                <div className="grid grid-cols-3 gap-2.5">
                  {items.map((item) => <ItemCard key={item.id} item={item} onClick={() => setSelected(item)} lang={lang} />)}
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
          background: 'var(--nav-bg, rgba(245,240,232,0.94))',
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
          <span className="text-xs font-medium tracking-wide">{tx.nav_library}</span>
        </button>
        <button
          onClick={() => switchTab('want')}
          className="flex-1 flex flex-col items-center py-3 gap-1"
          style={{ color: tab === 'want' ? 'var(--text)' : 'var(--text2)' }}
        >
          <IconBookmark size={20} />
          <span className="text-xs font-medium tracking-wide">{tx.nav_want}</span>
        </button>
        <button
          onClick={() => switchTab('discover')}
          className="flex-1 flex flex-col items-center py-3 gap-1"
          style={{ color: tab === 'discover' ? 'var(--text)' : 'var(--text2)' }}
        >
          <IconCompass size={20} />
          <span className="text-xs font-medium tracking-wide">{tx.nav_discover}</span>
        </button>
        <button
          onClick={() => switchTab('profile')}
          className="flex-1 flex flex-col items-center py-3 gap-1"
          style={{ color: tab === 'profile' ? 'var(--text)' : 'var(--text2)' }}
        >
          <IconPerson size={20} />
          <span className="text-xs font-medium tracking-wide">{tx.nav_profile}</span>
        </button>
      </nav>

      {selected && <ItemDrawer item={selected} onClose={() => setSelected(null)} lang={lang} />}
    </div>
  )
}
