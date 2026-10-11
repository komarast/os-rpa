import React, { useRef, useEffect } from 'react'
import { Terminal, ChevronUp, ChevronDown, Trash2, CheckCircle2, AlertTriangle, AlertCircle, Info } from 'lucide-react'
import type { ExecutionLogMessage } from '../types'

interface ConsolePanelProps {
  logs: ExecutionLogMessage[]
  isOpen: boolean
  onToggle: () => void
  onClear: () => void
  isRunning: boolean
  duration?: number
}

export const ConsolePanel: React.FC<ConsolePanelProps> = ({
  logs,
  isOpen,
  onToggle,
  onClear,
  isRunning,
  duration,
}) => {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (isOpen) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, isOpen])

  const getLogIcon = (level: string) => {
    switch (level) {
      case 'SUCCESS':
        return <CheckCircle2 size={13} color="#34d399" />
      case 'ERROR':
        return <AlertCircle size={13} color="#f43f5e" />
      case 'WARNING':
        return <AlertTriangle size={13} color="#f59e0b" />
      case 'INFO':
      default:
        return <Info size={13} color="#38bdf8" />
    }
  }

  const getLogColor = (level: string) => {
    switch (level) {
      case 'SUCCESS':
        return '#34d399'
      case 'ERROR':
        return '#f43f5e'
      case 'WARNING':
        return '#f59e0b'
      case 'INFO':
      default:
        return '#cbd5e1'
    }
  }

  return (
    <div
      style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        backgroundColor: '#0f172a',
        borderTop: '1px solid #334155',
        display: 'flex',
        flexDirection: 'column',
        zIndex: 20,
        transition: 'height 0.2s ease',
        height: isOpen ? 220 : 36,
      }}
    >
      {/* Console Header Bar */}
      <div
        style={{
          height: 36,
          padding: '0 16px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: isOpen ? '1px solid #1e293b' : 'none',
          cursor: 'pointer',
          userSelect: 'none',
        }}
        onClick={onToggle}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Terminal size={14} color="#38bdf8" />
          <span style={{ fontSize: 12, fontWeight: 700, color: '#f8fafc', letterSpacing: '0.04em' }}>
            EXECUTION CONSOLE
          </span>
          <span
            style={{
              fontSize: 11,
              backgroundColor: '#1e293b',
              color: '#94a3b8',
              padding: '1px 6px',
              borderRadius: 10,
            }}
          >
            {logs.length} events
          </span>
          {isRunning && (
            <span style={{ fontSize: 11, color: '#38bdf8', animation: 'pulse 1.5s infinite' }}>
              ● Robot Executing...
            </span>
          )}
          {duration !== undefined && !isRunning && (
            <span style={{ fontSize: 11, color: '#34d399' }}>Finished in {duration}s</span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {isOpen && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                onClear()
              }}
              style={{
                background: 'none',
                border: 'none',
                color: '#64748b',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                fontSize: 11,
              }}
              title="Clear logs"
            >
              <Trash2 size={12} /> Clear
            </button>
          )}
          {isOpen ? <ChevronDown size={16} color="#94a3b8" /> : <ChevronUp size={16} color="#94a3b8" />}
        </div>
      </div>

      {/* Log Messages Output */}
      {isOpen && (
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '8px 16px',
            fontFamily: 'monospace',
            fontSize: 12,
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
          }}
        >
          {logs.length === 0 ? (
            <div style={{ color: '#64748b', fontStyle: 'italic', padding: '8px 0' }}>
              No execution logs yet. Click 'Run Robot' above to execute the workflow.
            </div>
          ) : (
            logs.map((l, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, lineHeight: '1.4' }}>
                <span style={{ color: '#475569', fontSize: 11, flexShrink: 0 }}>
                  {l.timestamp ? l.timestamp.split('T')[1]?.slice(0, 8) : ''}
                </span>
                <span style={{ display: 'flex', alignItems: 'center', flexShrink: 0, marginTop: 2 }}>
                  {getLogIcon(l.level)}
                </span>
                {l.node_id && (
                  <span
                    style={{
                      color: '#a78bfa',
                      backgroundColor: '#2e1065',
                      padding: '0 4px',
                      borderRadius: 3,
                      fontSize: 10,
                      flexShrink: 0,
                    }}
                  >
                    [{l.node_id}]
                  </span>
                )}
                <span style={{ color: getLogColor(l.level), wordBreak: 'break-all' }}>{l.message}</span>
              </div>
            ))
          )}
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  )
}

