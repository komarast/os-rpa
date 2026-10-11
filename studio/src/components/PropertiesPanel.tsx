import React from 'react'
import Editor from '@monaco-editor/react'
import type { ActionDef } from '../types'
import type { Node } from '@xyflow/react'

interface PropertiesPanelProps {
  selectedNode: Node | null
  actionDef: ActionDef | null
  onUpdateParams: (nodeId: string, params: Record<string, any>) => void
  onUpdateMetadata: (nodeId: string, name?: string, output?: string) => void
}

export const PropertiesPanel: React.FC<PropertiesPanelProps> = ({
  selectedNode,
  actionDef,
  onUpdateParams,
  onUpdateMetadata,
}) => {
  if (!selectedNode) {
    return (
      <div
        style={{
          width: 320,
          height: '100%',
          backgroundColor: '#0f172a',
          borderLeft: '1px solid #334155',
          padding: 16,
          color: '#64748b',
          fontSize: 13,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          textAlign: 'center',
        }}
      >
        Select a node on the canvas to configure its properties
      </div>
    )
  }

  const nodeData = selectedNode.data as any
  const params = nodeData.params || {}

  const handleParamChange = (key: string, value: any) => {
    onUpdateParams(selectedNode.id, {
      ...params,
      [key]: value,
    })
  }

  return (
    <div
      style={{
        width: 340,
        height: '100%',
        backgroundColor: '#0f172a',
        borderLeft: '1px solid #334155',
        display: 'flex',
        flexDirection: 'column',
        overflowY: 'auto',
      }}
    >
      {/* Header */}
      <div style={{ padding: '14px 16px', borderBottom: '1px solid #334155' }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: '#f8fafc', marginBottom: 2 }}>
          ACTIVITY PROPERTIES
        </div>
        <div style={{ fontSize: 11, color: '#38bdf8' }}>{nodeData.type}</div>
        {actionDef?.description && (
          <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>
            {actionDef.description}
          </div>
        )}
      </div>

      <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
        {/* Step Name */}
        <div>
          <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#94a3b8', marginBottom: 4 }}>
            Step Name / Label
          </label>
          <input
            type="text"
            value={nodeData.name || ''}
            placeholder={nodeData.type}
            onChange={(e) => onUpdateMetadata(selectedNode.id, e.target.value, nodeData.output)}
            style={{
              width: '100%',
              backgroundColor: '#1e293b',
              border: '1px solid #334155',
              borderRadius: 6,
              padding: '6px 10px',
              color: '#f8fafc',
              fontSize: 12,
              outline: 'none',
            }}
          />
        </div>

        {/* Output Variable */}
        <div>
          <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#94a3b8', marginBottom: 4 }}>
            Output Variable (optional)
          </label>
          <input
            type="text"
            value={nodeData.output || ''}
            placeholder="e.g. current_item, total_sum"
            onChange={(e) => onUpdateMetadata(selectedNode.id, nodeData.name, e.target.value)}
            style={{
              width: '100%',
              backgroundColor: '#1e293b',
              border: '1px solid #334155',
              borderRadius: 6,
              padding: '6px 10px',
              color: '#38bdf8',
              fontSize: 12,
              outline: 'none',
            }}
          />
        </div>

        <div style={{ height: 1, backgroundColor: '#334155', margin: '4px 0' }} />

        {/* Dynamic Parameters */}
        {actionDef &&
          Object.entries(actionDef.params_schema).map(([key, schema]) => {
            const currentVal = params[key] !== undefined ? params[key] : schema.default

            if (schema.type === 'code' || nodeData.type === 'script.python') {
              return (
                <div key={key}>
                  <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#94a3b8', marginBottom: 4 }}>
                    {schema.label || key} (Python Script)
                  </label>
                  <div
                    style={{
                      height: 240,
                      border: '1px solid #334155',
                      borderRadius: 6,
                      overflow: 'hidden',
                    }}
                  >
                    <Editor
                      height="100%"
                      defaultLanguage="python"
                      theme="vs-dark"
                      value={typeof currentVal === 'string' ? currentVal : ''}
                      onChange={(val) => handleParamChange(key, val || '')}
                      options={{
                        minimap: { enabled: false },
                        fontSize: 12,
                        scrollBeyondLastLine: false,
                        automaticLayout: true,
                        tabSize: 4,
                      }}
                    />
                  </div>
                </div>
              )
            }

            if (schema.type === 'select' && schema.options) {
              return (
                <div key={key}>
                  <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#94a3b8', marginBottom: 4 }}>
                    {schema.label || key}
                  </label>
                  <select
                    value={currentVal || ''}
                    onChange={(e) => handleParamChange(key, e.target.value)}
                    style={{
                      width: '100%',
                      backgroundColor: '#1e293b',
                      border: '1px solid #334155',
                      borderRadius: 6,
                      padding: '6px 10px',
                      color: '#f8fafc',
                      fontSize: 12,
                      outline: 'none',
                    }}
                  >
                    {schema.options.map((opt) => (
                      <option key={opt} value={opt}>
                        {opt}
                      </option>
                    ))}
                  </select>
                </div>
              )
            }

            if (schema.type === 'boolean') {
              return (
                <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <input
                    type="checkbox"
                    id={`param-${key}`}
                    checked={Boolean(currentVal)}
                    onChange={(e) => handleParamChange(key, e.target.checked)}
                    style={{ cursor: 'pointer' }}
                  />
                  <label htmlFor={`param-${key}`} style={{ fontSize: 12, color: '#f8fafc', cursor: 'pointer' }}>
                    {schema.label || key}
                  </label>
                </div>
              )
            }

            // Default: string / number / object input
            const stringifiedVal =
              typeof currentVal === 'object' && currentVal !== null
                ? JSON.stringify(currentVal)
                : currentVal !== undefined
                ? String(currentVal)
                : ''

            return (
              <div key={key}>
                <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#94a3b8', marginBottom: 4 }}>
                  {schema.label || key}
                </label>
                <input
                  type={schema.type === 'number' ? 'number' : 'text'}
                  value={stringifiedVal}
                  placeholder={`Expression or value (e.g. {{item['name']}})`}
                  onChange={(e) => {
                    let val: any = e.target.value
                    if (schema.type === 'number') {
                      val = val === '' ? '' : Number(val)
                    } else if (schema.type === 'object' || schema.type === 'array') {
                      try {
                        val = JSON.parse(val)
                      } catch {
                        // keep as string while typing
                      }
                    }
                    handleParamChange(key, val)
                  }}
                  style={{
                    width: '100%',
                    backgroundColor: '#1e293b',
                    border: '1px solid #334155',
                    borderRadius: 6,
                    padding: '6px 10px',
                    color: '#f8fafc',
                    fontSize: 12,
                    outline: 'none',
                  }}
                />
              </div>
            )
          })}
      </div>
    </div>
  )
}

