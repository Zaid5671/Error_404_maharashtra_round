// The agents the frontend knows, by Run.agent name. Add a new agent's plugin here.

import { GenericTaskForm, GenericTaskSummary, genericResultLine, genericStepLabel } from './generic'
import { pizzaPlugin } from './pizza'
import type { AgentPlugin, ResolvedPlugin } from './types'

const PLUGINS: Record<string, AgentPlugin> = {
  pizza: pizzaPlugin,
}

export function getPlugin(name: string): ResolvedPlugin {
  const plugin: AgentPlugin = PLUGINS[name] ?? {
    name,
    title: name,
    defaultTask: {},
    TaskForm: GenericTaskForm,
  }
  return {
    ...plugin,
    TaskSummary: plugin.TaskSummary ?? GenericTaskSummary,
    resultLine: plugin.resultLine ?? genericResultLine,
    hiddenFaults: plugin.hiddenFaults ?? [],
    stepLabel: (step) => (step.error ? `error: ${step.error}` : (plugin.stepLabel?.(step) ?? genericStepLabel(step))),
  }
}
