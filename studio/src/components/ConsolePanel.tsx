import React, { useRef, useEffect, useState } from 'react'
import {
  Terminal,
  ChevronUp,
  ChevronDown,
  Trash2,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  Info,
  Variable,
  Layers,
  Bot,
  Play,
  RotateCw,
} from 'lucide-react'
import type { ExecutionLogMessage, StepHistoryItem, BotInfo } from '../types'

interface ConsolePanelProps {
  logs: ExecutionLogMessage[]
  variables: Record<string, any>
  stepHistory: StepHistoryItem[]
  bots: BotInfo[]
  isOpen: boolean
  onToggle: () => void
  onClear: () => void
  isRunning: boolean
  isPaused: boolean
  duration?: number
  onRefreshBots?: () => void
  onTriggerOnBot?: (botId: string) => void
}

export const ConsolePanel: React.FC<ConsolePanelProps> = ({
  logs,
  variables,
  stepHistory,
  bots,
  isOpen,
  onToggle,
  onClear,
  isRunning,
  isPaused,
  duration,
  onRefreshBots,
  onTriggerOnBot,
}) => {
  const [activeTab, setActiveTab] = useState<'logs' | 'variables' | 'history' | 'bots'>('logs')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (isOpen && activeTab === 'logs') {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, isOpen, activeTab])

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
        height: isOpen ? 260 : 38,
      }}
    >
      {/* Console Header Bar */}
      <div
        style={{
          height: 38,
          padding: '0 16px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: isOpen ? '1px solid #1e293b' : 'none',
          userSelect: 'none',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {/* Tab buttons */}
          <button
            onClick={() => setActiveTab('logs')}
            style={{
              background: activeTab === 'logs' ? '#1e293b' : 'none',
              border: 'none',
              borderRadius: 4,
              color: activeTab === 'logs' ? '#38bdf8' : '#94a3b8',
              fontWeight: 600,
              fontSize: 12,
              padding: '4px 8px',
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              cursor: 'pointer',
            }}
          >
            <Terminal size={13} />
            LOGS ({logs.length})
          </button>

          <button
            onClick={() => setActiveTab('variables')}
            style={{
              background: activeTab === 'variables' ? '#1e293b' : 'none',
              border: 'none',
              borderRadius: 4,
              color: activeTab === 'variables' ? '#c084fc' : '#94a3b8',
              fontWeight: 600,
              fontSize: 12,
              padding: '4px 8px',
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              cursor: 'pointer',
            }}
          >
            <Variable size={13} />
            VARIABLES ({Object.keys(variables).length})
          </button>

          <button
            onClick={() => setActiveTab('history')}
            style={{
              background: activeTab === 'history' ? '#1e293b' : 'none',
              border: 'none',
              borderRadius: 4,
              color: activeTab === 'history' ? '#34d399' : '#94a3b8',
              fontWeight: 600,
              fontSize: 12,
              padding: '4px 8px',
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              cursor: 'pointer',
            }}
          >
            <Layers size={13} />
            CALL STACK ({stepHistory.length})
          </button>

          <button
            onClick={() => setActiveTab('bots')}
            style={{
              background: activeTab === 'bots' ? '#1e293b' : 'none',
              border: 'none',
              borderRadius: 4,
              color: activeTab === 'bots' ? '#f59e0b' : '#94a3b8',
              fontWeight: 600,
              fontSize: 12,
              padding: '4px 8px',
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              cursor: 'pointer',
            }}
          >
            <Bot size={13} />
            BOTS ({bots.filter((b) => b.is_online).length} ONLINE)
          </button>

          {isRunning && !isPaused && (
            <span style={{ fontSize: 11, color: '#38bdf8', marginLeft: 8, animation: 'pulse 1.5s infinite' }}>
              ● Running...
            </span>
          )}
          {isPaused && (
            <span style={{ fontSize: 11, color: '#f59e0b', marginLeft: 8, fontWeight: 700 }}>
              ⏸ Paused at Breakpoint
            </span>
          )}
          {duration !== undefined && !isRunning && (
            <span style={{ fontSize: 11, color: '#34d399', marginLeft: 8 }}>Done in {duration}s</span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {activeTab === 'logs' && isOpen && (
            <button
              onClick={onClear}
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

          {activeTab === 'bots' && (
            <button
              onClick={onRefreshBots}
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
              title="Refresh Bots"
            >
              <RotateCw size={12} /> Refresh
            </button>
          )}

          <div onClick={onToggle} style={{ cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
            {isOpen ? <ChevronDown size={16} color="#94a3b8" /> : <ChevronUp size={16} color="#94a3b8" />}
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      {isOpen && (
        <div style={{ flex: 1, overflowY: 'auto', padding: '8px 16px' }}>
          {/* TAB 1: LOGS */}
          {activeTab === 'logs' && (
            <div
              style={{
                fontFamily: 'monospace',
                fontSize: 12,
                display: 'flex',
                flexDirection: 'column',
                gap: 4,
              }}
            >
              {logs.length === 0 ? (
                <div style={{ color: '#64748b', fontStyle: 'italic', padding: '8px 0' }}>
                  No execution logs yet. Click 'Run' or 'Debug' to execute workflow.
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

          {/* TAB 2: LIVE VARIABLES WATCHER */}
          {activeTab === 'variables' && (
            <div>
              {Object.keys(variables).length === 0 ? (
                <div style={{ color: '#64748b', fontStyle: 'italic', padding: '8px 0' }}>
                  No runtime variables currently set. Variables will appear dynamically during execution.
                </div>
              ) : (
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, fontFamily: 'monospace' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid #334155', color: '#94a3b8', textAlign: 'left' }}>
                      <th style={{ padding: '6px 8px' }}>VARIABLE</th>
                      <th style={{ padding: '6px 8px' }}>TYPE</th>
                      <th style={{ padding: '6px 8px' }}>VALUE</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(variables).map(([k, v]) => (
                      <tr key={k} style={{ borderBottom: '1px solid #1e293b' }}>
                        <td style={{ padding: '6px 8px', color: '#c084fc', fontWeight: 600 }}>{k}</td>
                        <td style={{ padding: '6px 8px', color: '#64748b' }}>
                          {Array.isArray(v) ? 'array' : typeof v}
                        </td>
                        <td style={{ padding: '6px 8px', color: '#38bdf8', wordBreak: 'break-all' }}>
                          {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {/* TAB 3: CALL STACK & STEP HISTORY */}
          {activeTab === 'history' && (
            <div>
              {stepHistory.length === 0 ? (
                <div style={{ color: '#64748b', fontStyle: 'italic', padding: '8px 0' }}>
                  No steps executed yet.
                </div>
              ) : (
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, fontFamily: 'monospace' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid #334155', color: '#94a3b8', textAlign: 'left' }}>
                      <th style={{ padding: '6px 8px' }}>#</th>
                      <th style={{ padding: '6px 8px' }}>NODE ID</th>
                      <th style={{ padding: '6px 8px' }}>ACTIVITY</th>
                      <th style={{ padding: '6px 8px' }}>STATUS</th>
                      <th style={{ padding: '6px 8px' }}>OUTPUT PREVIEW</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stepHistory.map((step, idx) => (
                      <tr key={idx} style={{ borderBottom: '1px solid #1e293b' }}>
                        <td style={{ padding: '6px 8px', color: '#64748b' }}>{idx + 1}</td>
                        <td style={{ padding: '6px 8px', color: '#a78bfa' }}>{step.nodeId}</td>
                        <td style={{ padding: '6px 8px', color: '#f8fafc' }}>{step.nodeName || step.nodeType}</td>
                        <td style={{ padding: '6px 8px' }}>
                          <span
                            style={{
                              color:
                                step.status === 'success'
                                  ? '#34d399'
                                  : step.status === 'error'
                                  ? '#f43f5e'
                                  : step.status === 'paused'
                                  ? '#f59e0b'
                                  : '#38bdf8',
                              fontWeight: 600,
                            }}
                          >
                            {step.status.toUpperCase()}
                          </span>
                        </td>
                        <td style={{ padding: '6px 8px', color: '#cbd5e1' }}>
                          {step.resultPreview || '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {/* TAB 4: UNATTENDED BOTS */}
          {activeTab === 'bots' && (
            <div>
              {bots.length === 0 ? (
                <div style={{ color: '#64748b', fontStyle: 'italic', padding: '8px 0' }}>
                  No remote unattended bots connected. Launch an agent with:
                  <div
                    style={{
                      marginTop: 6,
                      backgroundColor: '#1e293b',
                      padding: '6px 10px',
                      borderRadius: 4,
                      color: '#38bdf8',
                      fontFamily: 'monospace',
                    }}
                  >
                    python -m os_rpa.cli agent start --server ws://localhost:8000/ws/agent
                  </div>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {bots.map((b) => (
                    <div
                      key={b.bot_id}
                      style={{
                        backgroundColor: '#1e293b',
                        border: '1px solid #334155',
                        borderRadius: 6,
                        padding: '10px 14px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div
                          style={{
                            width: 10,
                            height: 10,
                            borderRadius: '50%',
                            backgroundColor: b.is_online ? '#10b981' : '#64748b',
                            boxShadow: b.is_online ? '0 0 8px #10b981' : 'none',
                          }}
                        />
                        <div>
                          <div style={{ fontSize: 13, fontWeight: 700, color: '#f8fafc' }}>
                            {b.bot_id} ({b.hostname})
                          </div>
                          <div style={{ fontSize: 11, color: '#94a3b8' }}>
                            OS: {b.system?.os || 'Windows'} &bull; Status: {b.status} &bull; User: {b.system?.username || 'runner'}
                          </div>
                        </div>
                      </div>

                      {onTriggerOnBot && (
                        <button
                          onClick={() => onTriggerOnBot(b.bot_id)}
                          disabled={!b.is_online || b.status === 'BUSY'}
                          style={{
                            backgroundColor: b.is_online && b.status !== 'BUSY' ? '#38bdf8' : '#334155',
                            color: b.is_online && b.status !== 'BUSY' ? '#0f172a' : '#64748b',
                            border: 'none',
                            borderRadius: 4,
                            padding: '6px 12px',
                            fontWeight: 700,
                            fontSize: 12,
                            display: 'flex',
                            alignItems: 'center',
                            gap: 6,
                            cursor: b.is_online && b.status !== 'BUSY' ? 'pointer' : 'not-allowed',
                          }}
                        >
                          <Play size={13} />
                          Dispatch to Bot
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
