export type ActionCategory =
  | 'flow'
  | 'http'
  | 'file'
  | 'queue'
  | 'web'
  | 'desktop'
  | 'excel'
  | 'script'
  | 'logic'
  | 'general'

export interface ActionParamSchema {
  type: 'string' | 'number' | 'boolean' | 'select' | 'object' | 'array' | 'code' | 'workflow' | 'any'
  label?: string
  required?: boolean
  default?: any
  options?: string[]
  language?: string
}

export interface ActionDef {
  type: string
  category: ActionCategory
  description: string
  params_schema: Record<string, ActionParamSchema>
}

export interface WorkflowNodeData {
  id: string
  type: string
  name?: string
  params: Record<string, any>
  output?: string
  executionState?: 'idle' | 'running' | 'success' | 'error' | 'paused'
  hasBreakpoint?: boolean
  label?: string
}

export interface WorkflowEdgeData {
  id: string
  source: string
  target: string
  sourceHandle?: string
  targetHandle?: string
  condition?: string
}

export interface Workflow {
  id: string
  name: string
  description?: string
  variables: Record<string, any>
  nodes: Array<{
    id: string
    type: string
    name?: string
    params: Record<string, any>
    output?: string
    position?: { x: number; y: number }
  }>
  edges: Array<{
    id: string
    source: string
    target: string
    source_handle?: string
    target_handle?: string
    condition?: string
  }>
}

export interface QueueItem {
  id: string
  queue_name: string
  payload: Record<string, any>
  status: 'NEW' | 'IN_PROGRESS' | 'SUCCESS' | 'FAILED' | 'ABANDONED'
  priority: number
  retry_count: number
  max_retries: number
  error_message?: string
  output_data?: Record<string, any>
  created_at: string
  updated_at: string
}

export interface QueueSummary {
  queue_name: string
  total_items: number
  new_items: number
  in_progress_items: number
  success_items: number
  failed_items: number
  abandoned_items: number
  last_activity?: string
}

export interface ExecutionLogMessage {
  timestamp: string
  level: 'INFO' | 'WARNING' | 'ERROR' | 'SUCCESS'
  node_id?: string
  message: string
  details?: Record<string, any>
}

export interface StepHistoryItem {
  nodeId: string
  nodeName: string
  nodeType: string
  timestamp: string
  status: 'running' | 'success' | 'error' | 'paused'
  resultPreview?: string
}

export type InspectTarget = 'desktop' | 'web'

export interface SelectorCandidate {
  kind: string
  value: string
  count: number
  unique: boolean
}

// Response of /api/inspector/pick and /api/inspector/validate
export interface InspectorResult {
  ok: boolean
  cancelled?: boolean
  error?: string
  target?: InspectTarget
  element?: Record<string, any>
  selectors?: SelectorCandidate[]
  // Suggested activity params (keys of web.* / desktop.* params_schema)
  params?: Record<string, any>
  warnings?: string[]
  found?: boolean
  count?: number
  unique?: boolean
}

// Open browser the web inspector can attach to (/api/inspector/browsers)
export interface BrowserInstance {
  endpoint: string
  port: number
  browser: string
  label: string
  source: 'workflow' | 'debug-port'
  pages: Array<{ title: string; url: string }>
}

export interface BotInfo {
  bot_id: string
  hostname: string
  status: 'IDLE' | 'BUSY' | 'OFFLINE'
  system: Record<string, any>
  connected_at?: string
  last_heartbeat?: string
  is_online: boolean
}
