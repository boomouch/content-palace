import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Content Palace',
  description: 'My personal library',
  icons: {
    icon: '/icon.svg',
    apple: '/icon.svg',
  },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen" style={{ background: 'var(--bg)' }}>
        {children}
      </body>
    </html>
  )
}
