// The pizza agent's task form and its collapsed summary.

import { Minus, Plus } from 'lucide-react'
import type { Order, OrderItem, Size } from '@/types/pizza'
import type { Json, TaskFormProps } from '../types'
import catalog from './catalog.json'
import { pizzaName } from './labels'

const field = 'grid gap-1 text-xs font-medium text-muted-foreground'
const control = 'h-8 min-w-0 rounded-md border bg-sunk px-2 text-sm text-foreground'
const COUPON_LABEL: Record<string, string> = Object.fromEntries(catalog.coupons.map((c) => [c.code, c.label]))

export function OrderForm({ task, onChange }: TaskFormProps) {
  const order = task as unknown as Order
  const update = (patch: Partial<Order>) => onChange({ ...order, ...patch } as unknown as Json)
  const setItem = (i: number, patch: Partial<OrderItem>) =>
    update({ items: order.items.map((item, j) => (j === i ? { ...item, ...patch } : item)) })

  return (
    <div className="grid gap-3.5">
      <div className="grid gap-1.5">
        {order.items.map((item, i) => (
          <div key={i} className="grid grid-cols-[minmax(0,1fr)_52px_52px_28px] items-center gap-1.5">
            <select id={`pizza-${i}`} aria-label={`Pizza ${i + 1}`} className={control} value={item.pizza}
              onChange={(e) => setItem(i, { pizza: e.target.value })}>
              {catalog.pizzas.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
            <select id={`size-${i}`} aria-label={`Size ${i + 1}`} className={control} value={item.size}
              onChange={(e) => setItem(i, { size: e.target.value as Size })}>
              {catalog.sizes.map((s) => <option key={s}>{s}</option>)}
            </select>
            <input id={`qty-${i}`} aria-label={`Quantity ${i + 1}`} className={control} type="number" min={1} max={9}
              value={item.qty} onChange={(e) => setItem(i, { qty: Math.max(1, Number(e.target.value) || 1) })} />
            <button type="button" aria-label={`Remove pizza ${i + 1}`} disabled={order.items.length === 1}
              className="grid h-8 place-items-center rounded-md border bg-sunk text-muted-foreground disabled:opacity-40"
              onClick={() => update({ items: order.items.filter((_, j) => j !== i) })}>
              <Minus className="size-3.5" />
            </button>
          </div>
        ))}
        <button type="button" className="inline-flex w-fit items-center gap-1 rounded-md border border-dashed px-2.5 py-1 text-xs text-muted-foreground"
          onClick={() => update({ items: [...order.items, { pizza: 'margherita', size: 'M', qty: 1 }] })}>
          <Plus className="size-3.5" /> Add pizza
        </button>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <label className={field} htmlFor="coupon">Coupon
          <select id="coupon" className={control} value={order.coupon ?? ''}
            onChange={(e) => update({ coupon: e.target.value || null })}>
            <option value="">No code (agent picks)</option>
            {catalog.coupons.map((c) => <option key={c.code} value={c.code}>{c.code}</option>)}
          </select>
        </label>
        <label className={field} htmlFor="area">Deliver to
          <select id="area" className={control} value={order.area} onChange={(e) => update({ area: e.target.value })}>
            {catalog.areas.map((a) => <option key={a.name} value={a.name}>{a.name}{a.deliverable ? '' : ' (no delivery)'}</option>)}
          </select>
        </label>
      </div>
      {order.coupon && <p className="m-0 text-xs text-muted-foreground">{COUPON_LABEL[order.coupon]}</p>}
    </div>
  )
}

export function OrderSummary({ task }: { task: Json }) {
  const order = task as unknown as Order
  return (
    <div className="grid gap-2.5">
      <ul className="m-0 grid list-none gap-1 p-0 text-[13px]">
        {order.items.map((i, k) => (
          <li key={k} className="flex justify-between gap-2"><span>{i.qty}× {pizzaName(i.pizza)}</span><span className="font-mono">{i.size}</span></li>
        ))}
      </ul>
      <div className="grid gap-0.5 text-xs text-muted-foreground">
        <span>Coupon: <span className="font-mono">{order.coupon ?? 'agent picks'}</span></span>
        <span>Deliver to: {order.area}</span>
      </div>
    </div>
  )
}
