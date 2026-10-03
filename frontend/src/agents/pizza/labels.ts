// Readable step labels and result sentences for the pizza agent.

import type { Step } from '@/types/contract'
import type { Order, OrderResult } from '@/types/pizza'
import type { ResultInfo } from '../types'
import catalog from './catalog.json'

const NAMES: Record<string, string> = Object.fromEntries(catalog.pizzas.map((p) => [p.id, p.name]))

export const pizzaName = (id: string) => NAMES[id] ?? id
const lower = (id: string) => pizzaName(id).toLowerCase()
export const rupees = (n: number) => `₹${n.toLocaleString('en-IN')}`

type Out = Record<string, any> // tool outputs are agent-defined JSON

export function pizzaStepLabel(step: Step): string | null {
  const o = step.output as Out
  switch (step.name) {
    case 'parse_order': {
      const order = o as Order
      const items = order.items.map((i) => `${i.qty}× ${lower(i.pizza)} ${i.size}`).join(', ')
      return `${items}${order.coupon ? ` · ${order.coupon}` : ''} · ${order.area}`
    }
    case 'search_menu': {
      const results = o.results as { id: string; prices: Record<string, number> }[]
      if (results.length === 1) {
        const prices = Object.entries(results[0].prices).map(([s, p]) => `${s} ${p}`).join(' / ')
        return `${pizzaName(results[0].id)} · ${prices}`
      }
      return `${String(step.input.query)}: ${results.length} pizzas`
    }
    case 'check_stock':
      return `${lower(o.pizza)} ${o.size} · ${o.available ? 'in stock' : 'out of stock'}`
    case 'add_to_cart': {
      const count = (o.cart as { qty: number }[]).reduce((n, l) => n + l.qty, 0)
      return `${count} pizza${count === 1 ? '' : 's'} · subtotal ${rupees(o.subtotal)}`
    }
    case 'apply_coupon':
      if (!o.valid) return `${o.code} · rejected (${o.reason})`
      return `${o.code} · ${o.type === 'pct' ? `${o.value}%` : rupees(o.value)} · −${rupees(o.discount)}`
    case 'check_delivery':
      return o.deliverable ? `${o.area} · fee ${rupees(o.delivery_fee)}` : `${o.area} · no delivery`
    case 'calculate_total':
      return `${rupees(o.subtotal)} − ${rupees(o.discount)} + ${rupees(o.delivery_fee)} = ${rupees(o.total)}`
    case 'place_order':
      return `placed · ${rupees(o.total)}`
  }
  return null
}

export function pizzaResultLine({ outcome, expected, actual }: ResultInfo): string {
  const exp = expected as OrderResult | null
  const act = actual as OrderResult | null
  if (outcome === 'success') {
    return act ? `Order placed for ${rupees(act.total)}, matching the expected total.` : "Correctly refused: we don't deliver there."
  }
  if (exp && act) return `Expected ${rupees(exp.total)}, but the agent charged ${rupees(act.total)}.`
  if (exp) return `The agent didn't place the order (expected ${rupees(exp.total)}).`
  return `The agent placed an order for ${rupees(act!.total)}, but this area isn't deliverable.`
}
