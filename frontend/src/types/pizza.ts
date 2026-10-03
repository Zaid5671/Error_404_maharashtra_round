// The pizza agent's own shapes: Run.task is an Order, Run.expected / Run.actual are OrderResults.
// Mirrors backend/agents/pizza/contract.py.

export type Size = 'S' | 'M' | 'L'

export interface OrderItem {
  pizza: string
  size: Size
  qty: number
}

export interface Order {
  items: OrderItem[]
  coupon: string | null
  area: string
}

export interface ResultItem extends OrderItem {
  unit_price: number
  line_total: number
}

export interface OrderResult {
  items: ResultItem[]
  subtotal: number
  coupon: string | null
  discount: number
  delivery_fee: number
  total: number
}

export interface Catalog {
  pizzas: { id: string; name: string; prices: Partial<Record<Size, number>> }[]
  sizes: Size[]
  coupons: { code: string; label: string }[]
  areas: { name: string; deliverable: boolean }[]
}
