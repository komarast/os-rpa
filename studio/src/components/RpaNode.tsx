import React from 'react'
import { Handle, Position } from '@xyflow/react'
import {
  Inbox,
  Globe,
  Monitor,
  FileSpreadsheet,
  Code2,
  GitBranch,
  Trash2,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Network,
  Folder,
  GitFork,
  PauseCircle,
  PlayCircle,
  StopCircle,
} from 'lucide-react'
import type { WorkflowNodeData, ActionCategory } from '../types'

interface RpaNodeProps {
  id: string
  data: WorkflowNodeData & {
    onDelete?: (id: string) => void
    onToggleBreakpoint?: (id: string) => void
  }
  selected?: boolean
}

export const getCategoryMeta = (category?: string) => {
  switch (category) {
    case 'flow':
      return { icon: GitFork, color: '#c084fc', bg: '#581c87', name: 'Control Flow' }
    case 'http':
      return { icon: Network, color: '#2dd4bf', bg: '#134e4a', name: 'HTTP & API' }
    case 'file':
      return { icon: Folder, color: '#fb923c', bg: '#7c2d12', name: 'File System' }
    case 'queue':
      return { icon: Inbox, color: '#f59e0b', bg: '#78350f', name: 'Queue' }
    case 'web':
      return { icon: Globe, color: '#38bdf8', bg: '#075985', name: 'Web' }
    case 'desktop':
      return { icon: Monitor, color: '#e879f9', bg: '#701a75', name: 'Desktop UI' }
    case 'excel':
      return { icon: FileSpreadsheet, color: '#34d399', bg: '#064e3b', name: 'Excel' }
    case 'script':
      return { icon: Code2, color: '#a78bfa', bg: '#4c1d95', name: 'Script' }
    case 'logic':
    default:
      return { icon: GitBranch, color: '#94a3b8', bg: '#334155', name: 'Logic' }
  }
}

export const getCategoryFromType = (type: string): ActionCategory => {
  if (type.startsWith('flow.')) return 'flow'
  if (type.startsWith('http.')) return 'http'
  if (type.startsWith('file.')) return 'file'
  if (type.startsWith('queue.')) return 'queue'
  if (type.startsWith('web.')) return 'web'
  if (type.startsWith('desktop.')) return 'desktop'
  if (type.startsWith('excel.')) return 'excel'
  if (type.startsWith('script.')) return 'script'
  return 'logic'
}

export const RpaNode: React.FC<RpaNodeProps> = ({ id, data, selected }) => {
  const category = getCategoryFromType(data.type)
  const meta = getCategoryMeta(category)
  const IconComponent = meta.icon

  const isStartNode = data.type === 'flow.start'
  const isEndNode = data.type === 'flow.end'
  const isDecisionNode = data.type === 'flow.if_else' || data.type === 'logic.condition'

  const getParamPreview = () => {
    if (!data.params) return ''
    if (data.params.condition) return `If: ${data.params.condition}`
    if (data.params.url) return `${data.params.url}`
    if (data.params.file_path) return `File: ${data.params.file_path}`
    if (data.params.source && data.params.destination) return `${data.params.source} -> ${data.params.destination}`
    if (data.params.queue_name) return `Queue: ${data.params.queue_name}`
    if (data.params.selector) return `Selector: ${data.params.selector}`
    if (data.params.message) return `"${data.params.message}"`
    if (data.params.assignments) return `${Object.keys(data.params.assignments).length} assignments`
    if (data.type === 'script.python') return 'Python Custom Code'
    return ''
  }

  // Border & shadow styling based on execution state
  let borderColor = '#334155'
  let boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.3)'

  if (selected) {
    borderColor = '#38bdf8'
  }
  if (data.executionState === 'running') {
    borderColor = '#38bdf8'
    boxShadow = '0 0 15px rgba(56, 189, 248, 0.7)'
  } else if (data.executionState === 'paused') {
    borderColor = '#f59e0b'
    boxShadow = '0 0 16px rgba(245, 158, 11, 0.8)'
  } else if (data.executionState === 'error') {
    borderColor = '#f43f5e'
  } else if (data.executionState === 'success') {
    borderColor = '#10b981'
  }

  return (
    <div
      style={{
        width: 250,
        backgroundColor: '#1e293b',
        borderRadius: 8,
        border: `2px solid ${borderColor}`,
        boxShadow,
        transition: 'all 0.15s ease-in-out',
        position: 'relative',
        userSelect: 'none',
      }}
    >
      {/* Target handle (all nodes except flow.start) */}
      {!isStartNode && (
        <Handle
          type="target"
          position={Position.Top}
          style={{ background: '#38bdf8', width: 10, height: 10 }}
        />
      )}

      {/* Breakpoint Badge on top-left corner */}
      <button
        onClick={(e) => {
          e.stopPropagation()
          data.onToggleBreakpoint?.(id)
        }}
        title={data.hasBreakpoint ? 'Remove Breakpoint' : 'Toggle Breakpoint'}
        style={{
          position: 'absolute',
          top: -8,
          left: -8,
          zIndex: 10,
          width: 18,
          height: 18,
          borderRadius: '50%',
          backgroundColor: data.hasBreakpoint ? '#ef4444' : '#334155',
          border: '2px solid #0f172a',
          cursor: 'pointer',
          padding: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: data.hasBreakpoint ? '0 0 8px #ef4444' : 'none',
          transition: 'all 0.15s ease',
        }}
      >
        {data.hasBreakpoint && (
          <div style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: '#ffffff' }} />
        )}
      </button>

      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 12px',
          borderBottom: '1px solid #334155',
          backgroundColor: isStartNode ? '#1e1b4b' : isEndNode ? '#31101e' : '#0f172a',
          borderTopLeftRadius: 6,
          borderTopRightRadius: 6,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div
            style={{
              padding: 4,
              borderRadius: 4,
              backgroundColor: meta.bg,
              color: meta.color,
              display: 'flex',
            }}
          >
            {isStartNode ? (
              <PlayCircle size={14} color="#a855f7" />
            ) : isEndNode ? (
              <StopCircle size={14} color="#f43f5e" />
            ) : (
              <IconComponent size={14} />
            )}
          </div>
          <span
            style={{
              fontSize: 11,
              fontWeight: 600,
              textTransform: 'uppercase',
              color: meta.color,
              letterSpacing: '0.05em',
            }}
          >
            {isStartNode ? 'START' : isEndNode ? 'END' : meta.name}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {data.executionState === 'running' && (
            <Loader2 size={14} color="#38bdf8" style={{ animation: 'spin 1s linear infinite' }} />
          )}
          {data.executionState === 'paused' && (
            <PauseCircle size={14} color="#f59e0b" style={{ animation: 'pulse 1s infinite' }} />
          )}
          {data.executionState === 'success' && <CheckCircle2 size={14} color="#34d399" />}
          {data.executionState === 'error' && <AlertCircle size={14} color="#f43f5e" />}
          {data.onDelete && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                data.onDelete?.(id)
              }}
              style={{
                background: 'none',
                border: 'none',
                color: '#64748b',
                cursor: 'pointer',
                padding: 2,
              }}
              title="Delete node"
            >
              <Trash2 size={13} />
            </button>
          )}
        </div>
      </div>

      {/* Body */}
      <div style={{ padding: '10px 12px' }}>
        <div
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: '#f8fafc',
            marginBottom: 4,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {data.name || data.type}
        </div>

        <div
          style={{
            fontSize: 11,
            color: '#94a3b8',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {getParamPreview() || data.type}
        </div>

        {data.output && (
          <div
            style={{
              marginTop: 6,
              display: 'inline-block',
              fontSize: 10,
              padding: '2px 6px',
              borderRadius: 4,
              backgroundColor: '#0f172a',
              color: '#38bdf8',
              border: '1px solid #1e3a8a',
            }}
          >
            &rarr; {data.output}
          </div>
        )}
      </div>

      {/* Output handles (all nodes except flow.end) */}
      {!isEndNode && (
        <>
          {isDecisionNode ? (
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0 20px', position: 'relative' }}>
              {/* True Handle */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                <span style={{ fontSize: 9, fontWeight: 700, color: '#22c55e', marginBottom: 2 }}>TRUE</span>
                <Handle
                  id="true"
                  type="source"
                  position={Position.Bottom}
                  style={{ left: '25%', background: '#22c55e', width: 10, height: 10 }}
                />
              </div>

              {/* False Handle */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                <span style={{ fontSize: 9, fontWeight: 700, color: '#ef4444', marginBottom: 2 }}>FALSE</span>
                <Handle
                  id="false"
                  type="source"
                  position={Position.Bottom}
                  style={{ left: '75%', background: '#ef4444', width: 10, height: 10 }}
                />
              </div>
            </div>
          ) : (
            <Handle
              type="source"
              position={Position.Bottom}
              style={{ background: '#38bdf8', width: 10, height: 10 }}
            />
          )}
        </>
      )}
    </div>
  )
}
