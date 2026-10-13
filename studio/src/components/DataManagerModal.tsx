import React, { useEffect, useMemo, useState } from 'react'
import type { Node } from '@xyflow/react'
import { Database, X, Plus, Trash2, AlertCircle } from 'lucide-react'
import type { VariableSnapshot } from '../variables'
import {
  findVariableDefinitions,
  findVariableUsages,
  formatPreview,
  isValidVariableName,
  valueType,
} from '../variables'

interface DataManagerModalProps {
  isOpen: boolean
  onClose: () => void
  workflowVariables: Record<string, any>
  onChangeWorkflowVariables: (vars: Record<string, any>) => void
  nodes: Node[]
  lastRun: VariableSnapshot
  onSelectNode: (nodeId: string) => void
}

type DraftType = 'string' | 'number' | 'boolean' | 'json'

interface DraftRow {
  key: number
  name: string
  type: DraftType
  text: string
}

const toDraftRow = (key: number, name: string, value: any): DraftRow => {
  if (typeof value === 'string') return { key, name, type: 'string', text: value }
  if (typeof value === 'number') return { key, name, type: 'number', text: String(value) }
  if (typeof value === 'boolean') return { key, name, type: 'boolean', text: String(value) }
  return { key, name, type: 'json', text: JSON.stringify(value, null, 0) ?? 'null' }
}

const parseDraftValue = (row: DraftRow): { value?: any; error?: string } => {
  switch (row.type) {
    case 'string':
      return { value: row.text }
    case 'number': {
      const n = Number(row.text)
      return row.text.trim() === '' || Number.isNaN(n) ? { error: 'Not a number' } : { value: n }
    }
    case 'boolean':
      return { value: row.text === 'true' }
    case 'json':
      try {
        return { value: JSON.parse(row.text) }
      } catch {
        return { error: 'Invalid JSON' }
      }
  }
}

const cell: React.CSSProperties = { padding: '7px 10px', borderBottom: '1px solid #1e293b', verticalAlign: 'top' }
const head: React.CSSProperties = { ...cell, color: '#94a3b8', fontWeight: 600, fontSize: 11, textAlign: 'left', position: 'sticky', top: 0, background: '#0f172a' }
const input: React.CSSProperties = {
  background: '#020617',
  border: '1px solid #334155',
  borderRadius: 4,
  color: '#e2e8f0',
  fontSize: 12,
  padding: '4px 6px',
  fontFamily: 'monospace',
  width: '100%',
  boxSizing: 'border-box',
}

const KIND_COLORS: Record<string, string> = {
  'workflow default': '#34d399',
  step: '#38bdf8',
  runtime: '#f59e0b',
}

export const DataManagerModal: React.FC<DataManagerModalProps> = ({
  isOpen,
  onClose,
  workflowVariables,
  onChangeWorkflowVariables,
  nodes,
  lastRun,
  onSelectNode,
}) => {
  const [tab, setTab] = useState<'overview' | 'defaults'>('overview')
  const [rows, setRows] = useState<DraftRow[]>([])
  const [nextKey, setNextKey] = useState(0)

  // Reset the draft editor whenever the modal opens or the workflow's variables change
  useEffect(() => {
    if (!isOpen) return
    const initial = Object.entries(workflowVariables).map(([k, v], i) => toDraftRow(i, k, v))
    setRows(initial)
    setNextKey(initial.length)
  }, [isOpen, workflowVariables])

  const nodeName = (id: string) => {
    const d = nodes.find((n) => n.id === id)?.data as any
    return d?.name || d?.type || id
  }

  const overview = useMemo(() => {
    const defs = findVariableDefinitions(nodes)
    const names = new Set<string>([
      ...Object.keys(workflowVariables),
      ...defs.map((d) => d.name),
      ...Object.keys(lastRun.variables),
    ])
    return [...names].sort().map((name) => {
      const definedBy = defs.filter((d) => d.name === name)
      const hasDefault = name in workflowVariables
      const kind = hasDefault ? 'workflow default' : definedBy.length ? 'step' : 'runtime'
      const hasRun = name in lastRun.variables
      return {
        name,
        kind,
        definedBy,
        defaultValue: workflowVariables[name],
        hasDefault,
        lastValue: lastRun.variables[name],
        hasRun,
        type: hasRun ? lastRun.meta[name]?.type || valueType(lastRun.variables[name]) : hasDefault ? valueType(workflowVariables[name]) : '—',
        usages: findVariableUsages(nodes, name),
      }
    })
  }, [nodes, workflowVariables, lastRun])

  const rowErrors = useMemo(() => {
    const errors: Record<number, string> = {}
    const seen = new Set<string>()
    rows.forEach((r) => {
      if (!isValidVariableName(r.name)) errors[r.key] = 'Name must be a valid identifier (letters, digits, _), not starting with _'
      else if (seen.has(r.name)) errors[r.key] = 'Duplicate name'
      else {
        const parsed = parseDraftValue(r)
        if (parsed.error) errors[r.key] = parsed.error
      }
      seen.add(r.name)
    })
    return errors
  }, [rows])

  const isDirty = useMemo(() => {
    if (Object.keys(rowErrors).length) return true
    const next: Record<string, any> = {}
    rows.forEach((r) => (next[r.name] = parseDraftValue(r).value))
    return JSON.stringify(next) !== JSON.stringify(workflowVariables)
  }, [rows, rowErrors, workflowVariables])

  if (!isOpen) return null

  const updateRow = (key: number, patch: Partial<DraftRow>) =>
    setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...patch } : r)))

  const addRow = (name = '') => {
    setRows((rs) => [...rs, { key: nextKey, name, type: 'string', text: '' }])
    setNextKey((k) => k + 1)
    setTab('defaults')
  }

  const applyDefaults = () => {
    if (Object.keys(rowErrors).length) return
    const next: Record<string, any> = {}
    rows.forEach((r) => (next[r.name] = parseDraftValue(r).value))
    onChangeWorkflowVariables(next)
  }

  const tabBtn = (id: typeof tab, label: string) => (
    <button
      onClick={() => setTab(id)}
      style={{
        background: tab === id ? '#1e293b' : 'none',
        border: 'none',
        borderBottom: tab === id ? '2px solid #2dd4bf' : '2px solid transparent',
        color: tab === id ? '#2dd4bf' : '#94a3b8',
        padding: '8px 14px',
        fontSize: 12,
        fontWeight: 600,
        cursor: 'pointer',
      }}
    >
      {label}
    </button>
  )

  const goToNode = (id: string) => {
    onSelectNode(id)
    onClose()
  }

  const nodeChip = (id: string) => (
    <span
      key={id}
      onClick={() => goToNode(id)}
      title="Select step on canvas"
      style={{
        display: 'inline-block',
        margin: '0 4px 2px 0',
        padding: '1px 6px',
        borderRadius: 4,
        background: '#1e293b',
        color: '#cbd5e1',
        fontSize: 11,
        cursor: 'pointer',
      }}
    >
      {nodeName(id)}
    </span>
  )

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
      onClick={onClose}
    >
      <div
        style={{
          width: '80%',
          maxWidth: 1000,
          height: '80%',
          maxHeight: 650,
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
            padding: '16px 20px',
            borderBottom: '1px solid #334155',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ backgroundColor: '#2dd4bf', color: '#0f172a', padding: 6, borderRadius: 6, display: 'flex' }}>
              <Database size={18} />
            </div>
            <div>
              <div style={{ fontSize: 16, fontWeight: 700, color: '#f8fafc' }}>Data Manager</div>
              <div style={{ fontSize: 12, color: '#94a3b8' }}>
                Workflow variables, the steps that create them, where they are used, and their last run values
              </div>
            </div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
            <X size={18} />
          </button>
        </div>

        <div style={{ display: 'flex', borderBottom: '1px solid #334155', paddingLeft: 10 }}>
          {tabBtn('overview', `All Variables (${overview.length})`)}
          {tabBtn('defaults', `Workflow Variables (${Object.keys(workflowVariables).length})`)}
        </div>

        <div style={{ flex: 1, overflow: 'auto', fontSize: 12 }}>
          {tab === 'overview' && (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={head}>NAME</th>
                  <th style={head}>DEFINED BY</th>
                  <th style={head}>TYPE</th>
                  <th style={head}>DEFAULT</th>
                  <th style={head}>LAST RUN VALUE</th>
                  <th style={head}>USED IN</th>
                </tr>
              </thead>
              <tbody>
                {overview.length === 0 && (
                  <tr>
                    <td colSpan={6} style={{ ...cell, color: '#64748b', fontStyle: 'italic' }}>
                      No variables yet. Add workflow variables, give steps an output variable, or run the workflow.
                    </td>
                  </tr>
                )}
                {overview.map((v) => (
                  <tr key={v.name}>
                    <td style={{ ...cell, fontFamily: 'monospace', color: '#c084fc', fontWeight: 600 }}>{v.name}</td>
                    <td style={cell}>
                      <span style={{ color: KIND_COLORS[v.kind], fontSize: 11, marginRight: 6 }}>{v.kind}</span>
                      <div>{v.definedBy.map((d) => nodeChip(d.nodeId))}</div>
                    </td>
                    <td style={{ ...cell, color: '#64748b', fontFamily: 'monospace' }}>{v.type}</td>
                    <td style={{ ...cell, fontFamily: 'monospace', color: '#34d399', wordBreak: 'break-all' }}>
                      {v.hasDefault ? formatPreview(v.defaultValue, 80) : <span style={{ color: '#475569' }}>—</span>}
                    </td>
                    <td style={{ ...cell, fontFamily: 'monospace', color: '#38bdf8', wordBreak: 'break-all', maxWidth: 260 }}>
                      {v.hasRun ? formatPreview(v.lastValue, 160) : <span style={{ color: '#475569' }}>not run</span>}
                    </td>
                    <td style={cell}>
                      {v.usages.length ? v.usages.map(nodeChip) : <span style={{ color: '#475569', fontSize: 11 }}>unused</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {tab === 'defaults' && (
            <div style={{ padding: '12px 16px' }}>
              <div style={{ color: '#94a3b8', marginBottom: 10 }}>
                Workflow variables are set before the first step runs. Reference them in step parameters as{' '}
                <code style={{ color: '#c084fc' }}>{'{{name}}'}</code>. Changes are saved with the workflow.
              </div>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th style={{ ...head, width: '22%' }}>NAME</th>
                    <th style={{ ...head, width: 110 }}>TYPE</th>
                    <th style={head}>DEFAULT VALUE</th>
                    <th style={{ ...head, width: 36 }} />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <React.Fragment key={r.key}>
                      <tr>
                        <td style={cell}>
                          <input
                            value={r.name}
                            onChange={(e) => updateRow(r.key, { name: e.target.value })}
                            placeholder="variable_name"
                            style={{ ...input, borderColor: rowErrors[r.key] ? '#f43f5e' : '#334155' }}
                          />
                        </td>
                        <td style={cell}>
                          <select
                            value={r.type}
                            onChange={(e) => {
                              const type = e.target.value as DraftType
                              updateRow(r.key, { type, text: type === 'boolean' ? 'false' : r.text })
                            }}
                            style={input}
                          >
                            <option value="string">Text</option>
                            <option value="number">Number</option>
                            <option value="boolean">Boolean</option>
                            <option value="json">JSON (list / object)</option>
                          </select>
                        </td>
                        <td style={cell}>
                          {r.type === 'boolean' ? (
                            <select value={r.text} onChange={(e) => updateRow(r.key, { text: e.target.value })} style={input}>
                              <option value="true">true</option>
                              <option value="false">false</option>
                            </select>
                          ) : (
                            <input
                              value={r.text}
                              onChange={(e) => updateRow(r.key, { text: e.target.value })}
                              placeholder={r.type === 'json' ? '{"key": "value"} or [1, 2]' : ''}
                              style={input}
                            />
                          )}
                        </td>
                        <td style={cell}>
                          <button
                            onClick={() => setRows((rs) => rs.filter((x) => x.key !== r.key))}
                            style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}
                            title="Remove variable"
                          >
                            <Trash2 size={14} />
                          </button>
                        </td>
                      </tr>
                      {rowErrors[r.key] && (
                        <tr>
                          <td colSpan={4} style={{ padding: '0 10px 6px', color: '#f43f5e', fontSize: 11 }}>
                            <AlertCircle size={11} style={{ verticalAlign: -1 }} /> {rowErrors[r.key]}
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
              <button
                onClick={() => addRow()}
                style={{
                  marginTop: 10,
                  background: '#1e293b',
                  border: '1px dashed #475569',
                  color: '#2dd4bf',
                  borderRadius: 6,
                  padding: '6px 12px',
                  fontSize: 12,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 5,
                }}
              >
                <Plus size={13} /> Add variable
              </button>
            </div>
          )}
        </div>

        {tab === 'defaults' && (
          <div
            style={{
              borderTop: '1px solid #334155',
              padding: '10px 16px',
              display: 'flex',
              justifyContent: 'flex-end',
              gap: 8,
            }}
          >
            <button
              onClick={() => {
                setRows(Object.entries(workflowVariables).map(([k, v], i) => toDraftRow(i, k, v)))
                setNextKey(Object.keys(workflowVariables).length)
              }}
              disabled={!isDirty}
              style={{
                background: 'none',
                border: '1px solid #334155',
                color: isDirty ? '#cbd5e1' : '#475569',
                borderRadius: 6,
                padding: '6px 12px',
                fontSize: 12,
                cursor: isDirty ? 'pointer' : 'default',
              }}
            >
              Discard
            </button>
            <button
              onClick={applyDefaults}
              disabled={!isDirty || Object.keys(rowErrors).length > 0}
              style={{
                background: isDirty && !Object.keys(rowErrors).length ? '#0d9488' : '#1e293b',
                border: 'none',
                color: '#ffffff',
                borderRadius: 6,
                padding: '6px 14px',
                fontSize: 12,
                fontWeight: 700,
                cursor: isDirty && !Object.keys(rowErrors).length ? 'pointer' : 'default',
              }}
            >
              Apply
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
