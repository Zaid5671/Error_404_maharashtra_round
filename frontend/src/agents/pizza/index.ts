// The pizza agent's frontend plugin.

import type { AgentPlugin } from '../types'
import { pizzaResultLine, pizzaStepLabel } from './labels'
import { OrderForm, OrderSummary } from './OrderForm'

export const pizzaPlugin: AgentPlugin = {
  name: 'pizza',
  title: 'Order',
  defaultTask: {
    items: [
      { pizza: 'paneer_tikka', size: 'S', qty: 1 },
      { pizza: 'veg_supreme', size: 'L', qty: 2 },
    ],
    coupon: 'PIZZA20',
    area: 'Bandra',
  },
  TaskForm: OrderForm,
  TaskSummary: OrderSummary,
  stepLabel: pizzaStepLabel,
  resultLine: pizzaResultLine,
  hiddenFaults: ['stock_lie'],
}
