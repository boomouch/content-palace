import Anthropic from '@anthropic-ai/sdk'
import { NextRequest, NextResponse } from 'next/server'

const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY })

export async function POST(req: NextRequest) {
  const { total, byType, topGenres, topVibes, byFeeling, topCreators, lang } = await req.json()
  const langInstruction = lang === 'ru' ? '\n\nReply in Russian.' : ''

  const prompt = `You are writing a personal taste profile for someone's content library app.

Their data:
- Total items: ${total}
- By type: ${JSON.stringify(byType)}
- Rating breakdown: ${JSON.stringify(byFeeling)}
- Top genres (from loved/essential items): ${topGenres.join(', ') || 'none yet'}
- Vibe tags (from loved/essential items): ${topVibes.join(', ') || 'none yet'}
- Favourite creators: ${topCreators.map(([c, n]: [string, number]) => `${c} (×${n})`).join(', ') || 'none yet'}

Write 2-3 sentences that feel like a genuine insight into this person's taste — not just a summary of the numbers. Find a pattern, make a specific observation, say something they might not have noticed about themselves. Be direct and specific. No fluff, no "based on your data". Just speak to them like you know their taste.${langInstruction}`

  const response = await client.messages.create({
    model: 'claude-haiku-4-5-20251001',
    max_tokens: 200,
    messages: [{ role: 'user', content: prompt }],
  })

  return NextResponse.json({ summary: (response.content[0] as { text: string }).text.trim() })
}
