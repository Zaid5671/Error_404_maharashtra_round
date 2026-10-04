import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

/** A bordered column panel with an uppercase title row. */
export function Panel({ title, sub, className, headerClassName, children }: { title?: ReactNode; sub?: ReactNode; className?: string; headerClassName?: string; children: ReactNode }) {
  return (
    <section className={cn('min-w-0 rounded-lg border bg-card', className)}>
      {title && (
        <header className={cn('flex flex-wrap items-baseline justify-between gap-2 border-b px-3.5 py-3', headerClassName)}>
          <h2 className="bb-title m-0">{title}</h2>
          {sub && <span className="text-xs text-muted-foreground">{sub}</span>}
        </header>
      )}
      {children}
    </section>
  )
}
