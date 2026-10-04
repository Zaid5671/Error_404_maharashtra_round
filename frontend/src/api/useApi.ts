// Load data for a screen: { data, error, loading }, reloaded when `deps` change.

import { useEffect, useState } from 'react'

export interface Loaded<T> {
  data: T | null
  error: string | null
  loading: boolean
}

export function useApi<T>(load: () => Promise<T>, deps: unknown[]): Loaded<T> {
  const [state, setState] = useState<Loaded<T>>({ data: null, error: null, loading: true })
  useEffect(() => {
    let live = true
    setState({ data: null, error: null, loading: true })
    load().then(
      (data) => live && setState({ data, error: null, loading: false }),
      (err: Error) => live && setState({ data: null, error: err.message, loading: false }),
    )
    return () => {
      live = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  return state
}
