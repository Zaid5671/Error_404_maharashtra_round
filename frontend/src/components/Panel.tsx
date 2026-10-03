import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

/** A bordered column panel with an uppercase title row. */
export function Panel({ title, sub, className, children }: { title?: string; sub?: ReactNode; className?: string; children: ReactNode }) {
  return (
    <section className={cn('min-w-0 rounded-lg border bg-card', className)}>
      {title && (
        <header className="flex items-baseline justify-between gap-2 border-b px-3.5 py-3">
          <h2 className="m-0 font-display text-[13px] font-bold tracking-[0.06em] uppercase">{title}</h2>
          {sub && <span className="text-xs text-muted-foreground">{sub}</span>}
        </header>
      )}
      {children}
    </section>
  )
}
