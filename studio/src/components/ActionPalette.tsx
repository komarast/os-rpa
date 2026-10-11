import React, { useState } from 'react'
import {
  Inbox,
  Globe,
  Monitor,
  FileSpreadsheet,
  Code2,
  GitBranch,
  Search,
  Plus,
} from 'lucide-react'
import type { ActionDef } from '../types'
import { getCategoryMeta } from './RpaNode'

interface ActionPaletteProps {
  actions: ActionDef[]
  onAddNode: (action: ActionDef) => void
}

export const ActionPalette: React.FC<ActionPaletteProps> = ({ actions, onAddNode }) => {
  const [search, setSearch] = useState('')
  const [selectedCat, setSelectedCat] = useState<string>('all')

  const categories: { id: string; label: string; icon: any }[] = [
    { id: 'all', label: 'All', icon: Search },
    { id: 'queue', label: 'Queue', icon: Inbox },
    { id: 'web', label: 'Web', icon: Globe },
    { id: 'desktop', label: 'Desktop', icon: Monitor },
    { id: 'excel', label: 'Excel', icon: FileSpreadsheet },
    { id: 'script', label: 'Script', icon: Code2 },
    { id: 'logic', label: 'Logic', icon: GitBranch },
  ]

  const filtered = actions.filter((act) => {
    const matchesCat = selectedCat === 'all' || act.category === selectedCat
    const matchesSearch =
      search.trim() === '' ||
      act.type.toLowerCase().includes(search.toLowerCase()) ||
      act.description.toLowerCase().includes(search.toLowerCase())
    return matchesCat && matchesSearch
  })

  return (
    <div
      style={{
        width: 280,
        height: '100%',
        backgroundColor: '#0f172a',
        borderRight: '1px solid #334155',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Palette Header */}
      <div style={{ padding: '12px 14px', borderBottom: '1px solid #334155' }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: '#f8fafc', marginBottom: 8, letterSpacing: '0.03em' }}>
          ACTIVITY PALETTE
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            backgroundColor: '#1e293b',
            border: '1px solid #334155',
            borderRadius: 6,
            padding: '4px 8px',
            gap: 6,
          }}
        >
          <Search size={14} color="#94a3b8" />
          <input
            type="text"
            placeholder="Search activities..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              background: 'none',
              border: 'none',
              outline: 'none',
              color: '#f8fafc',
              fontSize: 12,
              width: '100%',
            }}
          />
        </div>
      </div>

      {/* Category Pills */}
      <div
        style={{
          display: 'flex',
          gap: 4,
          padding: '8px 12px',
          overflowX: 'auto',
          borderBottom: '1px solid #1e293b',
        }}
      >
        {categories.map((c) => {
          const active = selectedCat === c.id
          return (
            <button
              key={c.id}
              onClick={() => setSelectedCat(c.id)}
              style={{
                fontSize: 11,
                padding: '3px 8px',
                borderRadius: 4,
                border: 'none',
                background: active ? '#38bdf8' : '#1e293b',
                color: active ? '#0f172a' : '#94a3b8',
                fontWeight: active ? 700 : 500,
                cursor: 'pointer',
                whiteSpace: 'nowrap',
              }}
            >
              {c.label}
            </button>
          )
        })}
      </div>

      {/* Activities List */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 6 }}>
        {filtered.map((act) => {
          const meta = getCategoryMeta(act.category)
          const Icon = meta.icon
          return (
            <div
              key={act.type}
              onClick={() => onAddNode(act)}
              style={{
                backgroundColor: '#1e293b',
                border: '1px solid #334155',
                borderRadius: 6,
                padding: '8px 10px',
                cursor: 'pointer',
                transition: 'border-color 0.1s ease',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = '#38bdf8'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = '#334155'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, overflow: 'hidden' }}>
                <div
                  style={{
                    backgroundColor: meta.bg,
                    color: meta.color,
                    padding: 4,
                    borderRadius: 4,
                    display: 'flex',
                  }}
                >
                  <Icon size={14} />
                </div>
                <div style={{ overflow: 'hidden' }}>
                  <div
                    style={{
                      fontSize: 12,
                      fontWeight: 600,
                      color: '#f8fafc',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {act.type}
                  </div>
                  <div
                    style={{
                      fontSize: 10,
                      color: '#94a3b8',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {act.description}
                  </div>
                </div>
              </div>
              <Plus size={14} color="#64748b" />
            </div>
          )
        })}
      </div>
    </div>
  )
}

