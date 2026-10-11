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
} from 'lucide-react'
import type { WorkflowNodeData, ActionCategory } from '../types'

interface RpaNodeProps {
  id: string
  data: WorkflowNodeData & {
    onDelete?: (id: string) => void
  }
  selected?: boolean
}

export const getCategoryMeta = (category?: string) => {
  switch (category) {
    case 'queue':
      return { icon: Inbox, color: '#f59e0b', bg: '#78350f', name: 'Queue' }
    case 'web':
      return { icon: Globe, color: '#38bdf8', bg: '#075985', name: 'Web' }
    case 'desktop':
      return { icon: Monitor, color: '#c084fc', bg: '#581c87', name: 'Desktop UI' }
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

  const getParamPreview = () => {
    if (!data.params) return ''
    if (data.params.queue_name) return `Queue: ${data.params.queue_name}`
    if (data.params.url) return `${data.params.url}`
    if (data.params.selector) return `Selector: ${data.params.selector}`
    if (data.params.file_path) return `File: ${data.params.file_path}`
    if (data.params.message) return `"${data.params.message}"`
    if (data.type === 'script.python') return 'Python Custom Code'
    return ''
  }

  return (
    <div
      style={{
        width: 250,
        backgroundColor: '#1e293b',
        borderRadius: 8,
        border: selected ? '2px solid #38bdf8' : '1px solid #334155',
        boxShadow: data.executionState === 'running' 
          ? '0 0 15px rgba(56, 189, 248, 0.6)' 
          : '0 4px 6px -1px rgba(0, 0, 0, 0.3)',
        transition: 'all 0.15s ease-in-out',
        position: 'relative',
        userSelect: 'none',
      }}
    >
      <Handle type="target" position={Position.Top} style={{ background: '#38bdf8' }} />

      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 12px',
          borderBottom: '1px solid #334155',
          backgroundColor: '#0f172a',
          borderTopLeftRadius: 7,
          borderTopRightRadius: 7,
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
            <IconComponent size={14} />
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
            {meta.name}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {data.executionState === 'running' && (
            <Loader2 size={14} color="#38bdf8" style={{ animation: 'spin 1s linear infinite' }} />
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

      <Handle type="source" position={Position.Bottom} style={{ background: '#38bdf8' }} />
    </div>
  )
}

