import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Variable, X, Search, Pencil, Trash2, Plus, ChevronRight, ChevronDown, Check } from 'lucide-react'
import type { VariableSnapshot } from '../variables'
import { formatPreview, formatPretty, isValidVariableName, parseValueInput, valueType } from '../variables'

interface DebugVariablesPanelProps {
  snapshot: VariableSnapshot
  nodeNames: Record<string, string>
  isPaused: boolean
  isRunning: boolean
  bottomOffset: number
  error?: string | null
  onSetVariable: (name: string, value: any) => void
  onDeleteVariable: (name: string) => void
  onSelectNode: (nodeId: string) => void
  onClose: () => void
}

const SOURCE_LABELS: Record<string, string> = {
  workflow: 'workflow default',
  input: 'run input',
  queue: 'queue item',
  debugger: 'edited in debugger',
}

const btn: React.CSSProperties = {
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  color: '#94a3b8',
  padding: 2,
  display: 'flex',
  alignItems: 'center',
}

export const DebugVariablesPanel: React.FC<DebugVariablesPanelProps> = ({
  snapshot,
  nodeNames,
  isPaused,
  isRunning,
  bottomOffset,
  error,
  onSetVariable,
  onDeleteVariable,
  onSelectNode,
  onClose,
}) => {
  const [filter, setFilter] = useState('')
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const [editing, setEditing] = useState<string | null>(null)
  const [editText, setEditText] = useState('')
  const [newName, setNewName] = useState('')
  const [newValue, setNewValue] = useState('')

  // Highlight variables whose value changed since the previous snapshot
  const prevRef = useRef<Record<string, string>>({})
  const [changed, setChanged] = useState<Set<string>>(new Set())
  useEffect(() => {
    const current: Record<string, string> = {}
    const diff = new Set<string>()
    Object.entries(snapshot.variables).forEach(([k, v]) => {
      current[k] = JSON.stringify(v)
      if (prevRef.current[k] !== current[k]) diff.add(k)
    })
    // Only show diffs once there was a previous state to compare against
    setChanged(Object.keys(prevRef.current).length > 0 ? diff : new Set())
    prevRef.current = current
  }, [snapshot])

  const entries = useMemo(() => {
    const q = filter.trim().toLowerCase()
    return Object.entries(snapshot.variables)
      .filter(([k, v]) => !q || k.toLowerCase().includes(q) || formatPreview(v, 500).toLowerCase().includes(q))
      .sort(([a], [b]) => a.localeCompare(b))
  }, [snapshot, filter])

  const sourceLabel = (src: string | null | undefined) => {
    if (!src) return null
    if (SOURCE_LABELS[src]) return { text: SOURCE_LABELS[src], nodeId: null }
    return { text: nodeNames[src] || src, nodeId: src }
  }

  const startEdit = (name: string) => {
    setEditing(name)
    setEditText(formatPretty(snapshot.variables[name]))
  }

  const commitEdit = () => {
    if (editing) onSetVariable(editing, parseValueInput(editText))
    setEditing(null)
  }

  const addVariable = () => {
    if (!isValidVariableName(newName)) return
    onSetVariable(newName, parseValueInput(newValue))
    setNewName('')
    setNewValue('')
  }

  const status = isPaused ? 'PAUSED' : isRunning ? 'RUNNING' : 'FINISHED'
  const statusColor = isPaused ? '#f59e0b' : isRunning ? '#38bdf8' : '#34d399'

  return (
    <div
      style={{
        position: 'absolute',
        top: 12,
        right: 12,
        bottom: bottomOffset + 12,
        width: 340,
        backgroundColor: 'rgba(15, 23, 42, 0.97)',
        border: '1px solid #334155',
        borderRadius: 8,
        boxShadow: '0 8px 24px rgba(0,0,0,0.45)',
        display: 'flex',
        flexDirection: 'column',
        zIndex: 25,
        fontSize: 12,
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 10px',
          borderBottom: '1px solid #1e293b',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#c084fc', fontWeight: 700 }}>
          <Variable size={14} /> DEBUG VARIABLES ({Object.keys(snapshot.variables).length})
          <span
            style={{
              marginLeft: 4,
              fontSize: 10,
              color: statusColor,
              border: `1px solid ${statusColor}`,
              borderRadius: 4,
              padding: '0 4px',
            }}
          >
            {status}
          </span>
        </div>
        <button style={btn} onClick={onClose} title="Close panel">
          <X size={14} />
        </button>
      </div>

      {/* Search */}
      <div style={{ padding: '6px 10px', borderBottom: '1px solid #1e293b', display: 'flex', alignItems: 'center', gap: 6 }}>
        <Search size={12} color="#64748b" />
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter by name or value…"
          style={{
            flex: 1,
            background: 'transparent',
            border: 'none',
            outline: 'none',
            color: '#e2e8f0',
            fontSize: 12,
          }}
        />
      </div>

      {error && (
        <div style={{ padding: '6px 10px', color: '#f43f5e', borderBottom: '1px solid #1e293b' }}>{error}</div>
      )}

      {/* Variable list */}
      <div style={{ flex: 1, overflowY: 'auto', fontFamily: 'monospace' }}>
        {entries.length === 0 && (
          <div style={{ color: '#64748b', fontStyle: 'italic', padding: 12, fontFamily: 'inherit' }}>
            {filter ? 'No variables match the filter.' : 'No variables yet. They appear as steps execute.'}
          </div>
        )}
        {entries.map(([name, value]) => {
          const meta = snapshot.meta[name]
          const src = sourceLabel(meta?.source)
          const isOpen = !!expanded[name]
          const isComplex = value !== null && typeof value === 'object'
          return (
            <div
              key={name}
              style={{
                borderBottom: '1px solid #1e293b',
                padding: '6px 10px',
                backgroundColor: changed.has(name) ? 'rgba(245, 158, 11, 0.10)' : 'transparent',
                borderLeft: changed.has(name) ? '2px solid #f59e0b' : '2px solid transparent',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <button
                  style={{ ...btn, visibility: isComplex ? 'visible' : 'hidden' }}
                  onClick={() => setExpanded((p) => ({ ...p, [name]: !isOpen }))}
                >
                  {isOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                </button>
                <span style={{ color: '#c084fc', fontWeight: 600 }}>{name}</span>
                <span style={{ color: '#64748b', fontSize: 10 }}>{meta?.type ?? valueType(value)}</span>
                <span style={{ flex: 1 }} />
                {isPaused && (
                  <>
                    <button style={btn} onClick={() => startEdit(name)} title="Edit value">
                      <Pencil size={12} />
                    </button>
                    <button style={btn} onClick={() => onDeleteVariable(name)} title="Remove variable">
                      <Trash2 size={12} />
                    </button>
                  </>
                )}
              </div>

              {editing === name ? (
                <div style={{ marginTop: 4 }}>
                  <textarea
                    value={editText}
                    onChange={(e) => setEditText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) commitEdit()
                      if (e.key === 'Escape') setEditing(null)
                    }}
                    autoFocus
                    rows={Math.min(10, editText.split('\n').length + 1)}
                    style={{
                      width: '100%',
                      boxSizing: 'border-box',
                      background: '#020617',
                      color: '#e2e8f0',
                      border: '1px solid #38bdf8',
                      borderRadius: 4,
                      fontFamily: 'monospace',
                      fontSize: 11,
                      padding: 4,
                    }}
                  />
                  <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end', alignItems: 'center' }}>
                    <span style={{ color: '#64748b', fontSize: 10, marginRight: 'auto' }}>JSON value · Ctrl+Enter</span>
                    <button style={{ ...btn, color: '#94a3b8' }} onClick={() => setEditing(null)}>
                      <X size={12} />
                    </button>
                    <button style={{ ...btn, color: '#34d399' }} onClick={commitEdit}>
                      <Check size={12} />
                    </button>
                  </div>
                </div>
              ) : isOpen ? (
                <pre
                  style={{
                    margin: '4px 0 0 18px',
                    color: '#38bdf8',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-all',
                    maxHeight: 240,
                    overflowY: 'auto',
                  }}
                >
                  {formatPretty(value)}
                </pre>
              ) : (
                <div style={{ marginLeft: 18, color: '#38bdf8', wordBreak: 'break-all' }}>{formatPreview(value)}</div>
              )}

              {src && (
                <div style={{ marginLeft: 18, marginTop: 2, fontSize: 10, color: '#64748b', fontFamily: 'sans-serif' }}>
                  set by{' '}
                  {src.nodeId ? (
                    <span
                      onClick={() => onSelectNode(src.nodeId!)}
                      style={{ color: '#94a3b8', textDecoration: 'underline', cursor: 'pointer' }}
                      title="Select step on canvas"
                    >
                      {src.text}
                    </span>
                  ) : (
                    <span style={{ color: '#94a3b8' }}>{src.text}</span>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Add variable (only while paused) */}
      <div style={{ borderTop: '1px solid #1e293b', padding: '6px 10px' }}>
        {isPaused ? (
          <div style={{ display: 'flex', gap: 4 }}>
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="name"
              style={{
                width: 90,
                background: '#020617',
                border: `1px solid ${newName && !isValidVariableName(newName) ? '#f43f5e' : '#334155'}`,
                borderRadius: 4,
                color: '#e2e8f0',
                fontSize: 11,
                padding: '3px 6px',
                fontFamily: 'monospace',
              }}
            />
            <input
              value={newValue}
              onChange={(e) => setNewValue(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && addVariable()}
              placeholder='value (JSON, e.g. 5, "text", [1,2])'
              style={{
                flex: 1,
                background: '#020617',
                border: '1px solid #334155',
                borderRadius: 4,
                color: '#e2e8f0',
                fontSize: 11,
                padding: '3px 6px',
                fontFamily: 'monospace',
              }}
            />
            <button
              style={{ ...btn, color: isValidVariableName(newName) ? '#34d399' : '#475569' }}
              onClick={addVariable}
              disabled={!isValidVariableName(newName)}
              title="Add / set variable"
            >
              <Plus size={14} />
            </button>
          </div>
        ) : (
          <div style={{ color: '#64748b', fontSize: 11 }}>
            {isRunning ? 'Pause or hit a breakpoint to edit values.' : 'Run finished. Values shown are final.'}
          </div>
        )}
      </div>
    </div>
  )
}
