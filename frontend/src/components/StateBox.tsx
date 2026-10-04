// Loading and error states for a screen that fetches its data.

import { Link } from 'react-router'

export function Loading({ what }: { what: string }) {
  return <div className="grid h-60 place-items-center text-sm text-muted-foreground" role="status">Loading {what}…</div>
}

export function Problem({ message, back }: { message: string; back?: { to: string; label: string } }) {
  return (
    <div className="mx-auto mt-10 grid max-w-xl gap-3 rounded-lg border bg-card p-6" role="alert">
      <span className="bb-label text-bad">Something went wrong</span>
      <p className="m-0">{message}</p>
      {back && <Link to={back.to} className="w-fit rounded-md border bg-sunk px-3 py-1.5 font-medium">{back.label}</Link>}
    </div>
  )
}
