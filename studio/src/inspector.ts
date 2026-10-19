import type { ActionDef, BrowserInstance, InspectTarget, InspectorResult } from './types'

// Params the inspector can fill for each target
const WEB_KEYS = ['selector']
const DESKTOP_KEYS = ['name', 'automation_id', 'control_type', 'window_title', 'title']

/** Which inspector applies to an activity (null when it has no element-targeting params). */
export function inspectTargetFor(actionDef: ActionDef | null): InspectTarget | null {
  if (!actionDef) return null
  const keys = Object.keys(actionDef.params_schema)
  if (actionDef.category === 'web' && keys.includes('selector')) return 'web'
  if (actionDef.category === 'desktop' && keys.some((k) => DESKTOP_KEYS.includes(k))) return 'desktop'
  return null
}

/** Merges inspector params into a node's params, limited to keys the activity actually has. */
export function applyInspectorParams(
  actionDef: ActionDef,
  current: Record<string, any>,
  picked: Record<string, any>
): Record<string, any> {
  const allowed = actionDef.category === 'web' ? WEB_KEYS : DESKTOP_KEYS
  const next = { ...current }
  for (const key of allowed) {
    if (key in actionDef.params_schema && picked[key] !== undefined) next[key] = picked[key]
  }
  return next
}

/** First literal URL opened by the workflow, used as the inspector's start page. */
export function guessStartUrl(nodes: Array<{ data: any }>): string {
  for (const n of nodes) {
    const d = n.data || {}
    const url = d.params?.url
    if ((d.type === 'web.open_browser' || d.type === 'web.navigate') && typeof url === 'string' && !url.includes('{{')) {
      return url
    }
  }
  return ''
}

async function post(path: string, body?: any): Promise<InspectorResult> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail || detail
    } catch {
      // keep status text
    }
    return { ok: false, error: detail }
  }
  return res.json()
}

// Web pick source: attach to an open browser (CDP), any open browser window (accessibility), or a new window
export type WebSource = 'cdp' | 'window' | 'new'

export const pickElement = (
  target: InspectTarget,
  url: string,
  channel: string,
  source: WebSource = 'new',
  endpoint = ''
) => post('/api/inspector/pick', { target, url, channel, source, endpoint, timeout: 180 })

export const validateElement = (
  target: InspectTarget,
  params: Record<string, any>,
  url: string,
  channel: string,
  endpoint = ''
) => post('/api/inspector/validate', { target, params, url, channel, endpoint, timeout: 10 })

export async function listBrowsers(): Promise<BrowserInstance[]> {
  try {
    const res = await fetch('/api/inspector/browsers')
    return res.ok ? res.json() : []
  } catch {
    return []
  }
}

export const cancelInspection = () => post('/api/inspector/cancel')
