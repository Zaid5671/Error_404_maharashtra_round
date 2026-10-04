// The agent in the URL and what kind it is. Connected agents can run and replay in the app;
// imported agents only have traces, so those screens explain why they're unavailable.

import { createContext, useContext } from 'react'
import type { AgentInfo } from '@/types/dashboard'

export interface AgentContextValue {
  agent: string
  info: AgentInfo | null // null while the list loads
  agents: AgentInfo[]
  canRun: boolean
  online: boolean // the API answered
  refresh: () => void
}

export const AgentContext = createContext<AgentContextValue>({
  agent: 'pizza', info: null, agents: [], canRun: true, online: false, refresh: () => {},
})

export const useAgent = () => useContext(AgentContext)
