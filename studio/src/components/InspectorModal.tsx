import React, { useEffect, useState } from 'react'
import { Crosshair, Globe, Monitor, X, CheckCircle2, AlertTriangle, Copy, Plus, Loader2, RefreshCw } from 'lucide-react'
import type { BrowserInstance, InspectTarget, InspectorResult } from '../types'
import { cancelInspection, listBrowsers, pickElement, validateElement } from '../inspector'
import type { WebSource } from '../inspector'

interface InspectorModalProps {
  isOpen: boolean
  onClose: () => void
  initialTarget: InspectTarget
  defaultUrl: string
  // Set when opened from an activity's properties: "Apply" writes into that node
  targetNodeLabel?: string | null
  onApply?: (params: Record<string, any>) => void
  onCreateActivity: (type: string, params: Record<string, any>) => void
}

const ACTIVITY_SHORTCUTS: Record<InspectTarget, Array<[string, string]>> = {
  web: [
    ['web.click', 'Click'],
    ['web.type', 'Type Into'],
    ['web.get_text', 'Get Text'],
  ],
  desktop: [
    ['desktop.click', 'Click'],
    ['desktop.type', 'Type Into'],
    ['desktop.get_text', 'Get Text'],
    ['desktop.find_window', 'Find Window'],
  ],
}

const DESKTOP_FIELDS: Array<[string, string]> = [
  ['window_title', 'Window Title'],
  ['name', 'Name'],
  ['automation_id', 'Automation ID'],
  ['control_type', 'Control Type'],
]

const inputStyle: React.CSSProperties = {
  width: '100%',
  backgroundColor: '#1e293b',
  border: '1px solid #334155',
  borderRadius: 6,
  padding: '6px 10px',
  color: '#f8fafc',
  fontSize: 12,
  outline: 'none',
}

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: 11,
  fontWeight: 600,
  color: '#94a3b8',
  marginBottom: 4,
}

const buttonStyle = (color: string, filled = false): React.CSSProperties => ({
  backgroundColor: filled ? color : '#1e293b',
  border: filled ? 'none' : '1px solid #334155',
  color: filled ? '#0f172a' : color,
  borderRadius: 6,
  padding: '6px 12px',
  fontSize: 12,
  fontWeight: 700,
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  gap: 6,
})

export const InspectorModal: React.FC<InspectorModalProps> = ({
  isOpen,
  onClose,
  initialTarget,
  defaultUrl,
  targetNodeLabel,
  onApply,
  onCreateActivity,
}) => {
  const [target, setTarget] = useState<InspectTarget>(initialTarget)
  const [url, setUrl] = useState(defaultUrl)
  const [channel, setChannel] = useState('auto')
  const [busy, setBusy] = useState<'picking' | 'validating' | null>(null)
  const [result, setResult] = useState<InspectorResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selector, setSelector] = useState('')
  const [desktopParams, setDesktopParams] = useState<Record<string, string>>({})
  const [validation, setValidation] = useState<InspectorResult | null>(null)
  // Web source: 'cdp:<endpoint>' (open browser with debug port), 'window' (any open window) or 'new'
  const [browsers, setBrowsers] = useState<BrowserInstance[]>([])
  const [source, setSource] = useState('window')
  const [loadingBrowsers, setLoadingBrowsers] = useState(false)

  const refreshBrowsers = async () => {
    setLoadingBrowsers(true)
    const list = await listBrowsers()
    setBrowsers(list)
    setSource((s) =>
      s.startsWith('cdp:') && list.some((b) => `cdp:${b.endpoint}` === s)
        ? s
        : list.length
        ? `cdp:${list[0].endpoint}`
        : s.startsWith('cdp:')
        ? 'window'
        : s
    )
    setLoadingBrowsers(false)
  }

  useEffect(() => {
    if (!isOpen) return
    setTarget(initialTarget)
    setUrl(defaultUrl)
    setResult(null)
    setError(null)
    setValidation(null)
    setSelector('')
    setDesktopParams({})
    refreshBrowsers()
  }, [isOpen, initialTarget, defaultUrl])

  if (!isOpen) return null

  const pageUrl = (result?.element?.page_url as string) || url
  const sourceKind: WebSource = source.startsWith('cdp:') ? 'cdp' : (source as WebSource)
  const sourceEndpoint = sourceKind === 'cdp' ? source.slice(4) : ''
  // Validate inside an open browser when one shows the picked page (logins, navigation state are kept)
  const validateEndpoint =
    sourceEndpoint ||
    browsers.find((b) => b.pages.some((p) => pageUrl && p.url.split('#')[0] === pageUrl.split('#')[0]))?.endpoint ||
    ''

  const currentParams = (): Record<string, any> =>
    target === 'web'
      ? { selector, url: pageUrl }
      : { ...desktopParams, title: desktopParams.window_title || '' }

  const hasSelection = target === 'web' ? !!selector : !!(desktopParams.name || desktopParams.automation_id || desktopParams.window_title)

  const switchTarget = (t: InspectTarget) => {
    if (busy) return
    setTarget(t)
    setResult(null)
    setError(null)
    setValidation(null)
  }

  const handlePick = async () => {
    setBusy('picking')
    setError(null)
    setValidation(null)
    try {
      const res = await pickElement(target, url, channel, sourceKind, sourceEndpoint)
      if (!res.ok) {
        if (!res.cancelled) setError(res.error || 'Inspection failed')
        return
      }
      setResult(res)
      if (target === 'web') {
        setSelector(res.params?.selector || '')
      } else {
        const p = res.params || {}
        setDesktopParams({
          window_title: p.window_title || '',
          name: p.name || '',
          automation_id: p.automation_id || '',
          control_type: p.control_type || '',
        })
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(null)
    }
  }

  const handleValidate = async () => {
    setBusy('validating')
    setValidation(null)
    try {
      setValidation(await validateElement(target, currentParams(), pageUrl, channel, target === 'web' ? validateEndpoint : ''))
    } catch (e) {
      setValidation({ ok: false, error: String(e) })
    } finally {
      setBusy(null)
    }
  }

  const handleClose = () => {
    if (busy) cancelInspection()
    onClose()
  }

  const element = result?.element || {}
  const attributeRows = Object.entries(element).filter(
    ([k, v]) => k !== 'path' && k !== 'rect' && v !== '' && v !== null && v !== undefined
  )
  const path: Array<Record<string, string>> = Array.isArray(element.path) ? element.path : []

  const hint =
    target === 'desktop'
      ? 'Switch to the application, hover the element and press Ctrl to select it. Esc cancels.'
      : sourceKind === 'window'
      ? 'Switch to your browser, hover the element and press Ctrl to select it. Esc cancels.'
      : sourceKind === 'cdp'
      ? 'Switch to the open browser and click the element in any tab. F2 pauses picking (to navigate), Esc cancels.'
      : 'A browser window opened. Click the element to select it. Press F2 to pause picking (to log in or navigate), Esc cancels.'

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.75)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 50,
        backdropFilter: 'blur(2px)',
      }}
      onClick={handleClose}
    >
      <div
        style={{
          width: '80%',
          maxWidth: 860,
          maxHeight: '86%',
          backgroundColor: '#0f172a',
          border: '1px solid #334155',
          borderRadius: 12,
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
          overflow: 'hidden',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: '12px 16px',
            borderBottom: '1px solid #334155',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Crosshair size={16} color="#f472b6" />
            <span style={{ fontSize: 13, fontWeight: 700, color: '#f8fafc' }}>UI ELEMENT INSPECTOR</span>
            {targetNodeLabel && (
              <span style={{ fontSize: 11, color: '#94a3b8' }}>
                for <span style={{ color: '#38bdf8' }}>{targetNodeLabel}</span>
              </span>
            )}
          </div>
          <button onClick={handleClose} style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
            <X size={16} />
          </button>
        </div>

        <div style={{ padding: 16, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* Target + start options */}
          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', gap: 4 }}>
              {(['desktop', 'web'] as InspectTarget[]).map((t) => {
                const Icon = t === 'desktop' ? Monitor : Globe
                const active = target === t
                return (
                  <button
                    key={t}
                    onClick={() => switchTarget(t)}
                    style={{
                      ...buttonStyle(active ? '#38bdf8' : '#94a3b8', active),
                      opacity: busy && !active ? 0.5 : 1,
                    }}
                  >
                    <Icon size={13} /> {t === 'desktop' ? 'Desktop App' : 'Web Browser'}
                  </button>
                )
              })}
            </div>
            {target === 'web' && (
              <div style={{ flex: 1, minWidth: 260 }}>
                <label style={labelStyle}>Pick from</label>
                <div style={{ display: 'flex', gap: 4 }}>
                  <select value={source} onChange={(e) => setSource(e.target.value)} disabled={!!busy} style={inputStyle}>
                    {browsers.length > 0 && (
                      <optgroup label="Open browsers (full DOM selectors)">
                        {browsers.map((b) => (
                          <option key={b.endpoint} value={`cdp:${b.endpoint}`}>
                            {b.label} · {b.browser.split('/')[0]} · {b.pages.length} tab(s)
                            {b.pages[0] ? ` · ${b.pages[0].title || b.pages[0].url}` : ''}
                          </option>
                        ))}
                      </optgroup>
                    )}
                    <optgroup label="Other">
                      <option value="window">Any open browser window (hover + Ctrl)</option>
                      <option value="new">New browser window</option>
                    </optgroup>
                  </select>
                  <button
                    onClick={refreshBrowsers}
                    disabled={!!busy}
                    title="Refresh open browsers"
                    style={{ ...buttonStyle('#94a3b8'), padding: '6px 8px' }}
                  >
                    <RefreshCw size={13} style={loadingBrowsers ? { animation: 'spin 1s linear infinite' } : undefined} />
                  </button>
                </div>
              </div>
            )}
            {target === 'web' && sourceKind === 'new' && (
              <>
                <div style={{ flex: 1, minWidth: 220 }}>
                  <label style={labelStyle}>Start URL (optional)</label>
                  <input
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="https://portal.example.com/login"
                    style={inputStyle}
                  />
                </div>
                <div>
                  <label style={labelStyle}>Browser</label>
                  <select value={channel} onChange={(e) => setChannel(e.target.value)} style={inputStyle}>
                    {['auto', 'msedge', 'chrome', 'chromium'].map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>
              </>
            )}
            {busy === 'picking' ? (
              <button onClick={() => cancelInspection()} style={buttonStyle('#f43f5e')}>
                <X size={13} /> Cancel
              </button>
            ) : (
              <button onClick={handlePick} disabled={!!busy} style={buttonStyle('#f472b6', true)}>
                <Crosshair size={13} /> {result ? 'Indicate again' : 'Indicate element'}
              </button>
            )}
          </div>

          {busy === 'picking' && (
            <div
              style={{
                display: 'flex',
                gap: 8,
                alignItems: 'center',
                padding: '10px 12px',
                borderRadius: 6,
                background: '#1e1b4b',
                border: '1px solid #4338ca',
                color: '#c7d2fe',
                fontSize: 12,
              }}
            >
              <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> {hint}
            </div>
          )}

          {error && (
            <div style={{ padding: '8px 12px', borderRadius: 6, background: '#450a0a', color: '#fca5a5', fontSize: 12 }}>
              {error}
            </div>
          )}

          {result?.warnings?.map((w) => (
            <div
              key={w}
              style={{
                display: 'flex',
                gap: 6,
                alignItems: 'center',
                padding: '8px 12px',
                borderRadius: 6,
                background: '#422006',
                color: '#fcd34d',
                fontSize: 12,
              }}
            >
              <AlertTriangle size={13} /> {w}
            </div>
          ))}

          {result && (
            <>
              {/* Selector */}
              {target === 'web' ? (
                <div>
                  <label style={labelStyle}>Selector (pick a candidate or edit)</label>
                  <input
                    value={selector}
                    onChange={(e) => setSelector(e.target.value)}
                    style={{ ...inputStyle, fontFamily: 'Consolas, monospace', color: '#38bdf8' }}
                  />
                  <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {(result.selectors || []).map((c) => (
                      <div
                        key={c.value}
                        onClick={() => setSelector(c.value)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 8,
                          padding: '5px 8px',
                          borderRadius: 4,
                          cursor: 'pointer',
                          background: selector === c.value ? '#1e293b' : 'transparent',
                          border: `1px solid ${selector === c.value ? '#38bdf8' : '#1e293b'}`,
                        }}
                      >
                        <span
                          style={{
                            fontSize: 10,
                            fontWeight: 700,
                            color: '#94a3b8',
                            minWidth: 64,
                            textTransform: 'uppercase',
                          }}
                        >
                          {c.kind}
                        </span>
                        <span
                          style={{
                            flex: 1,
                            fontFamily: 'Consolas, monospace',
                            fontSize: 12,
                            color: '#e2e8f0',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {c.value}
                        </span>
                        <span
                          style={{
                            fontSize: 10,
                            fontWeight: 700,
                            padding: '1px 6px',
                            borderRadius: 4,
                            background: c.unique ? '#064e3b' : '#422006',
                            color: c.unique ? '#34d399' : '#fcd34d',
                          }}
                        >
                          {c.unique ? 'UNIQUE' : c.count < 0 ? 'UNVERIFIED' : `${c.count} MATCHES`}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                  {DESKTOP_FIELDS.map(([key, label]) => (
                    <div key={key}>
                      <label style={labelStyle}>{label}</label>
                      <input
                        value={desktopParams[key] || ''}
                        onChange={(e) => setDesktopParams((p) => ({ ...p, [key]: e.target.value }))}
                        style={{ ...inputStyle, fontFamily: 'Consolas, monospace', color: '#e879f9' }}
                      />
                    </div>
                  ))}
                </div>
              )}

              {/* Element details */}
              <div>
                <label style={labelStyle}>Element</label>
                {path.length > 0 && (
                  <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 6, lineHeight: 1.6 }}>
                    {path.map((p, i) => (
                      <span key={i}>
                        {i > 0 && <span style={{ color: '#475569' }}> â€º </span>}
                        <span style={{ color: i === path.length - 1 ? '#e879f9' : '#cbd5e1' }}>
                          {p.control_type}
                          {p.name ? ` '${p.name.slice(0, 30)}'` : ''}
                        </span>
                      </span>
                    ))}
                  </div>
                )}
                <div style={{ border: '1px solid #1e293b', borderRadius: 6, overflow: 'hidden' }}>
                  {attributeRows.map(([k, v]) => (
                    <div key={k} style={{ display: 'flex', fontSize: 12, borderBottom: '1px solid #1e293b' }}>
                      <div style={{ width: 140, padding: '4px 8px', color: '#94a3b8', background: '#111827' }}>{k}</div>
                      <div
                        style={{
                          flex: 1,
                          padding: '4px 8px',
                          color: '#e2e8f0',
                          fontFamily: 'Consolas, monospace',
                          wordBreak: 'break-all',
                        }}
                      >
                        {String(v)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {validation && (
                <div
                  style={{
                    display: 'flex',
                    gap: 6,
                    alignItems: 'center',
                    padding: '8px 12px',
                    borderRadius: 6,
                    fontSize: 12,
                    background: validation.ok && validation.found && validation.count === 1 ? '#064e3b' : '#422006',
                    color: validation.ok && validation.found && validation.count === 1 ? '#6ee7b7' : '#fcd34d',
                  }}
                >
                  {validation.ok && validation.found ? <CheckCircle2 size={13} /> : <AlertTriangle size={13} />}
                  {!validation.ok
                    ? validation.error
                    : !validation.found
                    ? 'No matching element found'
                    : validation.count === 1
                    ? 'Found exactly 1 matching element'
                    : `Found ${validation.count} matching elements; the first one will be used`}
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer actions */}
        {result && (
          <div
            style={{
              padding: '10px 16px',
              borderTop: '1px solid #334155',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              flexWrap: 'wrap',
            }}
          >
            <button onClick={handleValidate} disabled={!!busy || !hasSelection} style={buttonStyle('#34d399')}>
              {busy === 'validating' ? <Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} /> : <CheckCircle2 size={13} />} Validate
            </button>
            {target === 'web' && (
              <button onClick={() => navigator.clipboard?.writeText(selector)} style={buttonStyle('#94a3b8')}>
                <Copy size={13} /> Copy
              </button>
            )}
            <div style={{ width: 1, height: 22, background: '#334155' }} />
            <span style={{ fontSize: 11, color: '#94a3b8' }}>Add activity:</span>
            {ACTIVITY_SHORTCUTS[target].map(([type, label]) => (
              <button
                key={type}
                disabled={!hasSelection}
                onClick={() => {
                  onCreateActivity(type, currentParams())
                  onClose()
                }}
                style={buttonStyle('#38bdf8')}
              >
                <Plus size={12} /> {label}
              </button>
            ))}
            <div style={{ flex: 1 }} />
            {onApply && targetNodeLabel && (
              <button
                disabled={!hasSelection}
                onClick={() => {
                  onApply(currentParams())
                  onClose()
                }}
                style={buttonStyle('#38bdf8', true)}
              >
                Apply to {targetNodeLabel}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
