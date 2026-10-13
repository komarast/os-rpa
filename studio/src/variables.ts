import type { Node } from '@xyflow/react'

export interface VariableMeta {
  type: string
  source: string | null
}

export interface VariableSnapshot {
  variables: Record<string, any>
  meta: Record<string, VariableMeta>
}

export interface VariableDefinition {
  name: string
  nodeId: string
  nodeName: string
  how: string
}

const IDENTIFIER = /^[A-Za-z_][A-Za-z0-9_]*$/

export const isValidVariableName = (name: string) => IDENTIFIER.test(name) && !name.startsWith('_')

/** Python-style type label, matching the engine's snapshot types. */
export const valueType = (v: any): string => {
  if (v === null || v === undefined) return 'None'
  if (Array.isArray(v)) return 'list'
  if (typeof v === 'boolean') return 'bool'
  if (typeof v === 'number') return Number.isInteger(v) ? 'int' : 'float'
  if (typeof v === 'string') return 'str'
  return 'dict'
}

export const formatPreview = (v: any, max = 120): string => {
  const text = typeof v === 'string' ? JSON.stringify(v) : JSON.stringify(v) ?? String(v)
  return text.length > max ? text.slice(0, max) + '…' : text
}

export const formatPretty = (v: any): string => JSON.stringify(v, null, 2) ?? String(v)

/** Parses user input as JSON (numbers, booleans, objects, quoted strings); falls back to a raw string. */
export const parseValueInput = (text: string): any => {
  const trimmed = text.trim()
  if (trimmed === '') return ''
  try {
    return JSON.parse(trimmed)
  } catch {
    return text
  }
}

/** Variables a workflow's steps create, derived from node params (what the engine will set at runtime). */
export const findVariableDefinitions = (nodes: Node[]): VariableDefinition[] => {
  const defs: VariableDefinition[] = []
  for (const n of nodes) {
    const d = n.data as any
    const params = d.params || {}
    const base = { nodeId: n.id, nodeName: d.name || d.type }
    if (d.output) defs.push({ ...base, name: d.output, how: 'step output' })
    if (d.type === 'logic.set_variable' && params.variable_name) {
      defs.push({ ...base, name: String(params.variable_name), how: 'set variable' })
    }
    if (d.type === 'flow.assign' && params.assignments && typeof params.assignments === 'object') {
      Object.keys(params.assignments).forEach((k) => defs.push({ ...base, name: k, how: 'assign' }))
    }
    if (d.type === 'flow.start' && params.inputs && typeof params.inputs === 'object') {
      Object.keys(params.inputs).forEach((k) => defs.push({ ...base, name: k, how: 'start input' }))
    }
    if (d.type === 'flow.try_catch') {
      defs.push({ ...base, name: String(params.error_var || 'last_error'), how: 'error variable' })
    }
    if (d.type === 'flow.loop') defs.push({ ...base, name: 'loop', how: 'loop state' })
    if (d.type === 'queue.get_item') defs.push({ ...base, name: 'item', how: 'queue item' })
  }
  return defs
}

const collectStrings = (value: any, out: string[]) => {
  if (typeof value === 'string') out.push(value)
  else if (Array.isArray(value)) value.forEach((v) => collectStrings(v, out))
  else if (value && typeof value === 'object') Object.values(value).forEach((v) => collectStrings(v, out))
}

/** Node ids whose params reference `name` inside a {{ ... }} expression or in script/condition code. */
export const findVariableUsages = (nodes: Node[], name: string): string[] => {
  const word = new RegExp(`(^|[^A-Za-z0-9_.])${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?![A-Za-z0-9_])`)
  const used: string[] = []
  for (const n of nodes) {
    const d = n.data as any
    const strings: string[] = []
    collectStrings(d.params || {}, strings)
    const hit = strings.some((s) => {
      const exprs = [...s.matchAll(/\{\{(.+?)\}\}/g)].map((m) => m[1])
      // Script / condition params are plain code, not templates
      const isCode = d.type?.startsWith('script.') || d.type === 'flow.try_catch' || d.type === 'logic.condition' || d.type === 'flow.if_else'
      return exprs.some((e) => word.test(e)) || (isCode && word.test(s))
    })
    if (hit) used.push(n.id)
  }
  return used
}
