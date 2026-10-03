// Recorded runs the mock stream plays, per agent: a clean run and a faulted copy of the same order.

import type { Run } from '@/types/contract'
import pizzaClean from './pizza_clean.json'
import pizzaFaulted from './pizza_faulted.json'

export const SAMPLE_RUNS: Record<string, { clean: Run; faulted: Run }> = {
  // JSON imports widen string literals, hence the casts; backend tests validate these files
  pizza: { clean: pizzaClean as Run, faulted: pizzaFaulted as Run },
}
