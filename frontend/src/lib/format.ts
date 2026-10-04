/** A 0..1 score as a percentage. Near-certain scores read ">99%" and tiny ones "<1%", never "100%" or "0%". */
export const pct = (x: number) => (x > 0 && x < 0.01 ? '<1%' : x >= 0.995 && x < 1 ? '>99%' : `${Math.round(x * 100)}%`)

/** "12 s", "3.4 s", "1 min 5 s" */
export function duration(ms: number): string {
  if (ms < 10_000) return `${(ms / 1000).toFixed(1)} s`
  if (ms < 60_000) return `${Math.round(ms / 1000)} s`
  return `${Math.floor(ms / 60_000)} min ${Math.round((ms % 60_000) / 1000)} s`
}

/** "just now", "5 min ago", "3 h ago", "2 days ago" */
export function ago(iso: string): string {
  const s = (Date.now() - new Date(iso).getTime()) / 1000
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86_400) return `${Math.floor(s / 3600)} h ago`
  const d = Math.floor(s / 86_400)
  return `${d} day${d === 1 ? '' : 's'} ago`
}
