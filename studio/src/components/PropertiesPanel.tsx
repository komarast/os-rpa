import React, { useEffect, useState } from 'react'
import Editor from '@monaco-editor/react'
import { Crosshair, Download } from 'lucide-react'
import type { ActionDef } from '../types'
import type { Node } from '@xyflow/react'
import { inspectTargetFor } from '../inspector'

interface PropertiesPanelProps {
  selectedNode: Node | null
  actionDef: ActionDef | null
  currentWorkflowId: string
  onUpdateParams: (nodeId: string, params: Record<string, any>) => void
  onUpdateMetadata: (nodeId: string, name?: string, output?: string) => void
  onInspect: (nodeId: string) => void
}

const fieldStyle: React.CSSProperties = {
  width: '100%',
  backgroundColor: '#1e293b',
  border: '1px solid #334155',
  borderRadius: 6,
  padding: '6px 10px',
  color: '#f8fafc',
  fontSize: 12,
  outline: 'none',
}

/** Inputs a workflow declares: its workflow variables plus flow.start inputs, with defaults. */
const declaredInputs = (wf: any): Record<string, any> => {
  const inputs: Record<string, any> = { ...(wf.variables || {}) }
  for (const n of wf.nodes || []) {
    if (n.type === 'flow.start' && n.params?.inputs && typeof n.params.inputs === 'object') {
      Object.assign(inputs, n.params.inputs)
    }
  }
  return inputs
}

// Saved-workflow selector for flow.invoke_workflow; can prefill the arguments from the target's inputs
const WorkflowParamField: React.FC<{
  label: string
  value: string
  currentWorkflowId: string
  onChange: (value: string) => void
  onLoadArguments: (inputs: Record<string, any>) => void
}> = ({ label, value, currentWorkflowId, onChange, onLoadArguments }) => {
  const [workflows, setWorkflows] = useState<Array<{ id: string; name: string }>>([])
  const [status, setStatus] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/workflows')
      .then((r) => r.json())
      .then((data) => setWorkflows(data))
      .catch(() => setWorkflows([]))
  }, [])

  const known = workflows.some((w) => w.id === value)

  const loadArguments = async () => {
    setStatus(null)
    try {
      const res = await fetch(`/api/workflows/${encodeURIComponent(value)}`)
      if (!res.ok) throw new Error('Workflow not found')
      const inputs = declaredInputs(await res.json())
      onLoadArguments(inputs)
      setStatus(Object.keys(inputs).length ? `Loaded ${Object.keys(inputs).length} argument(s)` : 'Workflow declares no inputs')
    } catch (e) {
      setStatus(String(e))
    }
  }

  return (
    <div>
      <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#94a3b8', marginBottom: 4 }}>{label}</label>
      <select value={known ? value : value ? '__custom' : ''} onChange={(e) => e.target.value !== '__custom' && onChange(e.target.value)} style={fieldStyle}>
        <option value="">Select a saved workflow...</option>
        {workflows.map((w) => (
          <option key={w.id} value={w.id} disabled={w.id === currentWorkflowId}>
            {w.name} ({w.id}){w.id === currentWorkflowId ? ' - this workflow' : ''}
          </option>
        ))}
        {!known && value && <option value="__custom">{value}</option>}
      </select>
      <input
        type="text"
        value={value}
        placeholder="...or an id, name or path/to/workflow.json"
        onChange={(e) => onChange(e.target.value)}
        style={{ ...fieldStyle, marginTop: 6, fontSize: 11, color: '#94a3b8' }}
      />
      <button
        onClick={loadArguments}
        disabled={!value}
        style={{
          marginTop: 6,
          background: '#1e293b',
          border: '1px solid #334155',
          color: value ? '#c084fc' : '#64748b',
          borderRadius: 6,
          padding: '4px 10px',
          fontSize: 11,
          fontWeight: 600,
          cursor: value ? 'pointer' : 'not-allowed',
          display: 'flex',
          alignItems: 'center',
          gap: 5,
        }}
        title="Add the invoked workflow's input variables to Arguments (existing entries are kept)"
      >
        <Download size={12} /> Load arguments
      </button>
      {status && <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>{status}</div>}
    </div>
  )
}

export const PropertiesPanel: React.FC<PropertiesPanelProps> = ({
  selectedNode,
  actionDef,
  currentWorkflowId,
  onUpdateParams,
  onUpdateMetadata,
  onInspect,
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

        {/* Element inspector for web / desktop activities */}
        {inspectTargetFor(actionDef) && (
          <button
            onClick={() => onInspect(selectedNode.id)}
            style={{
              backgroundColor: '#1e293b',
              border: '1px solid #f472b6',
              color: '#f472b6',
              borderRadius: 6,
              padding: '7px 10px',
              fontSize: 12,
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 6,
            }}
            title={
              inspectTargetFor(actionDef) === 'web'
                ? 'Open a browser and click the element to generate its selector'
                : 'Hover the element in the application and press Ctrl to capture it'
            }
          >
            <Crosshair size={14} /> Indicate element on screen
          </button>
        )}

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

            if (schema.type === 'workflow') {
              return (
                <WorkflowParamField
                  key={key}
                  label={schema.label || key}
                  value={typeof currentVal === 'string' ? currentVal : ''}
                  currentWorkflowId={currentWorkflowId}
                  onChange={(val) => handleParamChange(key, val)}
                  onLoadArguments={(inputs) => {
                    const existing = params.arguments && typeof params.arguments === 'object' ? params.arguments : {}
                    onUpdateParams(selectedNode.id, { ...params, [key]: currentVal, arguments: { ...inputs, ...existing } })
                  }}
                />
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

