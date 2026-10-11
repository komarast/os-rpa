import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import {
  ReactFlow,
  Controls,
  Background,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
} from '@xyflow/react'
import type { Connection, Edge, Node } from '@xyflow/react'
import {
  Play,
  Save,
  Inbox,
  FolderOpen,
  Zap,
  Bug,
  Pause,
  SkipForward,
  Square,
  Gauge,
} from 'lucide-react'

import type { ActionDef, ExecutionLogMessage, Workflow, StepHistoryItem, BotInfo } from './types'
import { RpaNode } from './components/RpaNode'
import { ActionPalette } from './components/ActionPalette'
import { PropertiesPanel } from './components/PropertiesPanel'
import { QueueModal } from './components/QueueModal'
import { ConsolePanel } from './components/ConsolePanel'

// Default template: Queue Invoice & Excel Processor
const DEFAULT_TEMPLATE_NODES: Node[] = [
  {
    id: 'step_get_item',
    type: 'rpaNode',
    position: { x: 250, y: 60 },
    data: {
      id: 'step_get_item',
      type: 'queue.get_item',
      name: 'Fetch Next Queue Item',
      params: { queue_name: 'CustomerQueue' },
      output: 'current_item',
      executionState: 'idle',
    },
  },
  {
    id: 'step_custom_script',
    type: 'rpaNode',
    position: { x: 250, y: 220 },
    data: {
      id: 'step_custom_script',
      type: 'script.python',
      name: 'Calculate Discount Script',
      params: {
        code: `# Calculate processing fee and status
acc = item.get('account_id', 'UNKNOWN')
act = item.get('action', 'none')
status = 'VERIFIED' if act == 'verify' else 'PENDING'

context.set('processed_status', status)
context.set('account_name', f'Customer-{acc}')
output = {'status': status, 'account': acc}
print(f'Processed account {acc} with status {status}')
`,
      },
      output: 'calc_result',
      executionState: 'idle',
    },
  },
  {
    id: 'step_append_excel',
    type: 'rpaNode',
    position: { x: 250, y: 380 },
    data: {
      id: 'step_append_excel',
      type: 'excel.append_row',
      name: 'Write to Customer Excel Report',
      params: {
        file_path: 'data/customer_report.xlsx',
        sheet_name: 'Customers',
        row_data: ['{{account_name}}', '{{processed_status}}', 'Success'],
      },
      executionState: 'idle',
    },
  },
  {
    id: 'step_set_success',
    type: 'rpaNode',
    position: { x: 250, y: 540 },
    data: {
      id: 'step_set_success',
      type: 'queue.set_status',
      name: 'Mark Queue Item Complete',
      params: {
        status: 'SUCCESS',
        output_data: { result: '{{calc_result}}' },
      },
      executionState: 'idle',
    },
  },
]

const DEFAULT_TEMPLATE_EDGES: Edge[] = [
  { id: 'e1', source: 'step_get_item', target: 'step_custom_script' },
  { id: 'e2', source: 'step_custom_script', target: 'step_append_excel' },
  { id: 'e3', source: 'step_append_excel', target: 'step_set_success' },
]

export function App() {
  const [nodes, setNodes, onNodesChange] = useNodesState(DEFAULT_TEMPLATE_NODES)
  const [edges, setEdges, onEdgesChange] = useEdgesState(DEFAULT_TEMPLATE_EDGES)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [actions, setActions] = useState<ActionDef[]>([])
  const [workflowName, setWorkflowName] = useState('Customer Queue & Excel Robot')
  const [workflowId, setWorkflowId] = useState('wf_customer_processor')

  // Saved workflows list from backend
  const [savedWorkflows, setSavedWorkflows] = useState<Array<{ id: string; name: string }>>([])
  const [selectedDropdownKey, setSelectedDropdownKey] = useState<string>('template:queue_excel')

  const [isQueueModalOpen, setIsQueueModalOpen] = useState(false)
  const [isConsoleOpen, setIsConsoleOpen] = useState(true)
  const [logs, setLogs] = useState<ExecutionLogMessage[]>([])
  const [isRunning, setIsRunning] = useState(false)
  const [isDebugging, setIsDebugging] = useState(false)
  const [isPaused, setIsPaused] = useState(false)
  const [pausedNodeId, setPausedNodeId] = useState<string | null>(null)
  const [executionDuration, setExecutionDuration] = useState<number | undefined>(undefined)

  // Debugging controls
  const [stepDelay, setStepDelay] = useState<number>(0) // in ms
  const [liveVariables, setLiveVariables] = useState<Record<string, any>>({})
  const [stepHistory, setStepHistory] = useState<StepHistoryItem[]>([])
  const [bots, setBots] = useState<BotInfo[]>([])

  const debugSocketRef = useRef<WebSocket | null>(null)
  const nodeTypes = useMemo(() => ({ rpaNode: RpaNode }), [])

  // Fetch saved workflows from API
  const fetchSavedWorkflows = useCallback(async () => {
    try {
      const res = await fetch('/api/workflows')
      if (res.ok) {
        const data = await res.json()
        setSavedWorkflows(data)
      }
    } catch (err) {
      console.error('Failed to load workflows:', err)
    }
  }, [])

  // Fetch bots
  const fetchBots = useCallback(async () => {
    try {
      const res = await fetch('/api/bots')
      if (res.ok) {
        const data = await res.json()
        setBots(data)
      }
    } catch {
      // ignore
    }
  }, [])

  // Fetch available actions and saved workflows from API on mount
  useEffect(() => {
    fetch('/api/actions')
      .then((res) => res.json())
      .then((data) => setActions(data))
      .catch((err) => console.error('Failed to load actions:', err))

    fetchSavedWorkflows()
    fetchBots()
    const interval = setInterval(fetchBots, 5000)
    return () => clearInterval(interval)
  }, [fetchSavedWorkflows, fetchBots])

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  )

  const handleDeleteNode = useCallback(
    (id: string) => {
      setNodes((nds) => nds.filter((n) => n.id !== id))
      setEdges((eds) => eds.filter((e) => e.source !== id && e.target !== id))
      if (selectedNodeId === id) setSelectedNodeId(null)
    },
    [selectedNodeId, setNodes, setEdges]
  )

  const handleToggleBreakpoint = useCallback(
    (id: string) => {
      setNodes((nds) => {
        const updated = nds.map((n) => {
          if (n.id === id) {
            const currentBp = !!(n.data as any).hasBreakpoint
            return {
              ...n,
              data: {
                ...n.data,
                hasBreakpoint: !currentBp,
              },
            }
          }
          return n
        })

        // If currently debugging, send updated breakpoints to server
        if (debugSocketRef.current && debugSocketRef.current.readyState === WebSocket.OPEN) {
          const bps = updated.filter((n) => (n.data as any).hasBreakpoint).map((n) => n.id)
          debugSocketRef.current.send(JSON.stringify({ cmd: 'set_breakpoints', breakpoints: bps }))
        }

        return updated
      })
    },
    [setNodes]
  )

  // Attach delete & breakpoint handlers to nodes
  useEffect(() => {
    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        data: {
          ...n.data,
          onDelete: handleDeleteNode,
          onToggleBreakpoint: handleToggleBreakpoint,
        },
      }))
    )
  }, [handleDeleteNode, handleToggleBreakpoint, setNodes])

  const handleAddNode = (actionDef: ActionDef) => {
    const newId = `node_${Date.now().toString(36)}`
    const defaultParams: Record<string, any> = {}
    Object.entries(actionDef.params_schema).forEach(([k, schema]) => {
      if (schema.default !== undefined) {
        defaultParams[k] = schema.default
      }
    })

    const newNode: Node = {
      id: newId,
      type: 'rpaNode',
      position: {
        x: 200 + Math.random() * 100,
        y: 150 + Math.random() * 100,
      },
      data: {
        id: newId,
        type: actionDef.type,
        name: actionDef.type,
        params: defaultParams,
        executionState: 'idle',
        hasBreakpoint: false,
        onDelete: handleDeleteNode,
        onToggleBreakpoint: handleToggleBreakpoint,
      },
    }

    setNodes((nds) => [...nds, newNode])
    setSelectedNodeId(newId)
  }

  const handleUpdateParams = (nodeId: string, newParams: Record<string, any>) => {
    setNodes((nds) =>
      nds.map((n) => {
        if (n.id === nodeId) {
          return {
            ...n,
            data: {
              ...n.data,
              params: newParams,
            },
          }
        }
        return n
      })
    )
  }

  const handleUpdateMetadata = (nodeId: string, name?: string, output?: string) => {
    setNodes((nds) =>
      nds.map((n) => {
        if (n.id === nodeId) {
          return {
            ...n,
            data: {
              ...n.data,
              name: name !== undefined ? name : (n.data as any).name,
              output: output !== undefined ? output : (n.data as any).output,
            },
          }
        }
        return n
      })
    )
  }

  const selectedNode = nodes.find((n) => n.id === selectedNodeId) || null
  const selectedActionDef = selectedNode
    ? actions.find((a) => a.type === (selectedNode.data as any).type) || null
    : null

  // Build Workflow JSON
  const getWorkflowPayload = (): Workflow => {
    return {
      id: workflowId,
      name: workflowName,
      variables: {},
      nodes: nodes.map((n) => {
        const d = n.data as any
        return {
          id: n.id,
          type: d.type,
          name: d.name,
          params: d.params || {},
          output: d.output || null,
          position: n.position,
        }
      }),
      edges: edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        source_handle: e.sourceHandle || undefined,
        target_handle: e.targetHandle || undefined,
        condition: (e.data as any)?.condition,
      })),
    }
  }

  const handleSaveWorkflow = async () => {
    const targetId = workflowId.trim() || `wf_${Date.now()}`
    setWorkflowId(targetId)

    const wf = {
      ...getWorkflowPayload(),
      id: targetId,
      name: workflowName.trim() || 'Untitled Workflow',
    }

    try {
      const res = await fetch('/api/workflows', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(wf),
      })
      if (res.ok) {
        await fetchSavedWorkflows()
        setSelectedDropdownKey(`saved:${wf.id}`)
        alert(`Workflow "${wf.name}" saved successfully!`)
      }
    } catch (e) {
      alert('Failed to save workflow: ' + e)
    }
  }

  // Load a saved workflow from API
  const loadSavedWorkflow = async (wfId: string) => {
    try {
      const res = await fetch(`/api/workflows/${encodeURIComponent(wfId)}`)
      if (res.ok) {
        const data = await res.json()
        setWorkflowName(data.name || 'Untitled Workflow')
        setWorkflowId(data.id || wfId)

        const loadedNodes: Node[] = (data.nodes || []).map((n: any, idx: number) => ({
          id: n.id,
          type: 'rpaNode',
          position: n.position || { x: 250, y: 80 + idx * 140 },
          data: {
            id: n.id,
            type: n.type,
            name: n.name || n.type,
            params: n.params || {},
            output: n.output || null,
            executionState: 'idle',
            hasBreakpoint: false,
            onDelete: handleDeleteNode,
            onToggleBreakpoint: handleToggleBreakpoint,
          },
        }))

        const loadedEdges: Edge[] = (data.edges || []).map((e: any) => ({
          id: e.id || `e_${e.source}_${e.target}`,
          source: e.source,
          target: e.target,
          sourceHandle: e.source_handle,
          targetHandle: e.target_handle,
          data: { condition: e.condition },
        }))

        setNodes(loadedNodes)
        setEdges(loadedEdges)
        setSelectedNodeId(null)
        setSelectedDropdownKey(`saved:${wfId}`)
      }
    } catch (err) {
      alert('Failed to load workflow: ' + err)
    }
  }

  // Normal Run Workflow (Fast execution)
  const handleRunWorkflow = async () => {
    if (isRunning) return
    setIsRunning(true)
    setIsDebugging(false)
    setIsPaused(false)
    setIsConsoleOpen(true)
    setLogs([])
    setStepHistory([])
    setLiveVariables({})
    setExecutionDuration(undefined)

    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        data: { ...n.data, executionState: 'idle' },
      }))
    )

    const wf = getWorkflowPayload()
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/run`

    try {
      const socket = new WebSocket(wsUrl)

      socket.onopen = () => {
        socket.send(JSON.stringify({ workflow: wf, initial_variables: {} }))
      }

      socket.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          if (msg.event === 'log') {
            setLogs((prev) => [...prev, msg.data])
          } else if (msg.event === 'node_start') {
            setNodes((nds) =>
              nds.map((n) =>
                n.id === msg.node_id ? { ...n, data: { ...n.data, executionState: 'running' } } : n
              )
            )
            const nd = nodes.find((n) => n.id === msg.node_id)
            setStepHistory((prev) => [
              ...prev,
              {
                nodeId: msg.node_id,
                nodeName: (nd?.data as any)?.name || msg.node_id,
                nodeType: (nd?.data as any)?.type || '',
                timestamp: new Date().toLocaleTimeString(),
                status: 'running',
              },
            ])
          } else if (msg.event === 'node_complete') {
            setNodes((nds) =>
              nds.map((n) =>
                n.id === msg.node_id ? { ...n, data: { ...n.data, executionState: 'success' } } : n
              )
            )
            setStepHistory((prev) =>
              prev.map((s) =>
                s.nodeId === msg.node_id
                  ? { ...s, status: 'success', resultPreview: msg.result }
                  : s
              )
            )
          } else if (msg.event === 'finished') {
            setIsRunning(false)
            setExecutionDuration(msg.result.duration_seconds)
            setLiveVariables(msg.result.variables || {})
            socket.close()
          } else if (msg.event === 'error') {
            setIsRunning(false)
            alert('Execution error: ' + msg.message)
            socket.close()
          }
        } catch (e) {
          console.error(e)
        }
      }

      socket.onerror = async () => {
        setIsRunning(false)
      }
    } catch {
      setIsRunning(false)
    }
  }

  // Interactive Debug Execution (Breakpoints, Pause, Stepping, Slow-Motion)
  const handleStartDebug = () => {
    if (isRunning) {
      if (isPaused) {
        // Resume execution
        debugSocketRef.current?.send(JSON.stringify({ cmd: 'resume' }))
        setIsPaused(false)
        setNodes((nds) =>
          nds.map((n) =>
            n.id === pausedNodeId ? { ...n, data: { ...n.data, executionState: 'running' } } : n
          )
        )
      }
      return
    }

    setIsRunning(true)
    setIsDebugging(true)
    setIsPaused(false)
    setIsConsoleOpen(true)
    setLogs([])
    setStepHistory([])
    setLiveVariables({})
    setExecutionDuration(undefined)

    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        data: { ...n.data, executionState: 'idle' },
      }))
    )

    const wf = getWorkflowPayload()
    const activeBreakpoints = nodes.filter((n) => (n.data as any).hasBreakpoint).map((n) => n.id)
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/debug`

    const socket = new WebSocket(wsUrl)
    debugSocketRef.current = socket

    socket.onopen = () => {
      socket.send(
        JSON.stringify({
          workflow: wf,
          initial_variables: {},
          breakpoints: activeBreakpoints,
          step_delay: stepDelay / 1000,
        })
      )
    }

    socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.event === 'log') {
          setLogs((prev) => [...prev, msg.data])
        } else if (msg.event === 'node_start') {
          setNodes((nds) =>
            nds.map((n) =>
              n.id === msg.node_id ? { ...n, data: { ...n.data, executionState: 'running' } } : n
            )
          )
          const nd = nodes.find((n) => n.id === msg.node_id)
          setStepHistory((prev) => [
            ...prev,
            {
              nodeId: msg.node_id,
              nodeName: (nd?.data as any)?.name || msg.node_id,
              nodeType: (nd?.data as any)?.type || '',
              timestamp: new Date().toLocaleTimeString(),
              status: 'running',
            },
          ])
        } else if (msg.event === 'node_complete') {
          setNodes((nds) =>
            nds.map((n) =>
              n.id === msg.node_id ? { ...n, data: { ...n.data, executionState: 'success' } } : n
            )
          )
          setStepHistory((prev) =>
            prev.map((s) =>
              s.nodeId === msg.node_id
                ? { ...s, status: 'success', resultPreview: msg.result }
                : s
            )
          )
        } else if (msg.event === 'paused') {
          setIsPaused(true)
          setPausedNodeId(msg.node_id)
          setLiveVariables(msg.variables || {})
          setNodes((nds) =>
            nds.map((n) =>
              n.id === msg.node_id ? { ...n, data: { ...n.data, executionState: 'paused' } } : n
            )
          )
        } else if (msg.event === 'resumed') {
          setIsPaused(false)
          setPausedNodeId(null)
        } else if (msg.event === 'finished') {
          setIsRunning(false)
          setIsDebugging(false)
          setIsPaused(false)
          setExecutionDuration(msg.result.duration_seconds)
          setLiveVariables(msg.result.variables || {})
          socket.close()
        } else if (msg.event === 'error') {
          setIsRunning(false)
          setIsDebugging(false)
          alert('Debug error: ' + msg.message)
          socket.close()
        }
      } catch (e) {
        console.error(e)
      }
    }

    socket.onerror = () => {
      setIsRunning(false)
      setIsDebugging(false)
    }
  }

  // Debug controls
  const handleStepOver = () => {
    if (!isRunning || !isDebugging) return
    debugSocketRef.current?.send(JSON.stringify({ cmd: 'step' }))
  }

  const handlePause = () => {
    if (!isRunning || !isDebugging) return
    debugSocketRef.current?.send(JSON.stringify({ cmd: 'pause' }))
  }

  const handleStop = () => {
    if (!isRunning) return
    debugSocketRef.current?.send(JSON.stringify({ cmd: 'stop' }))
    setIsRunning(false)
    setIsDebugging(false)
    setIsPaused(false)
  }

  const handleStepDelayChange = (ms: number) => {
    setStepDelay(ms)
    if (debugSocketRef.current && debugSocketRef.current.readyState === WebSocket.OPEN) {
      debugSocketRef.current.send(JSON.stringify({ cmd: 'set_delay', delay: ms / 1000 }))
    }
  }

  // Trigger on remote bot
  const handleTriggerOnBot = async (botId: string) => {
    const wf = getWorkflowPayload()
    try {
      const res = await fetch('/api/jobs/trigger', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workflow: wf,
          target_bot_id: botId,
        }),
      })
      if (res.ok) {
        const data = await res.json()
        alert(`Dispatched job ${data.job_id} to bot '${botId}'! Check Unattended Bots tab.`)
        fetchBots()
      } else {
        const err = await res.text()
        alert('Failed to trigger bot: ' + err)
      }
    } catch (e) {
      alert('Error triggering bot: ' + e)
    }
  }

  // Hotkeys (F5 = Debug/Resume, F10 = Step Over)
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'F5') {
        e.preventDefault()
        handleStartDebug()
      } else if (e.key === 'F10') {
        e.preventDefault()
        handleStepOver()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  })

  const loadTemplate = (type: string) => {
    if (type === 'queue_excel') {
      setNodes(DEFAULT_TEMPLATE_NODES)
      setEdges(DEFAULT_TEMPLATE_EDGES)
      setWorkflowName('Customer Queue & Excel Robot')
      setWorkflowId('wf_customer_processor')
      setSelectedDropdownKey('template:queue_excel')
    } else if (type === 'web_automation') {
      setNodes([
        {
          id: 'w1',
          type: 'rpaNode',
          position: { x: 250, y: 100 },
          data: {
            id: 'w1',
            type: 'web.open_browser',
            name: 'Open Portal',
            params: { url: 'https://news.ycombinator.com', headless: false },
            output: 'page_info',
            executionState: 'idle',
          },
        },
        {
          id: 'w2',
          type: 'rpaNode',
          position: { x: 250, y: 260 },
          data: {
            id: 'w2',
            type: 'web.get_text',
            name: 'Extract Headline',
            params: { selector: '.titleline > a' },
            output: 'headline',
            executionState: 'idle',
          },
        },
        {
          id: 'w3',
          type: 'rpaNode',
          position: { x: 250, y: 420 },
          data: {
            id: 'w3',
            type: 'logic.log',
            name: 'Log Extracted Headline',
            params: { message: 'Top Headline: {{headline}}', level: 'INFO' },
            executionState: 'idle',
          },
        },
        {
          id: 'w4',
          type: 'rpaNode',
          position: { x: 250, y: 580 },
          data: {
            id: 'w4',
            type: 'web.close_browser',
            name: 'Close Browser',
            params: {},
            executionState: 'idle',
          },
        },
      ])
      setEdges([
        { id: 'e1', source: 'w1', target: 'w2' },
        { id: 'e2', source: 'w2', target: 'w3' },
        { id: 'e3', source: 'w3', target: 'w4' },
      ])
      setWorkflowName('Web News Scraper')
      setWorkflowId('wf_web_scraper')
      setSelectedDropdownKey('template:web_automation')
    } else {
      setNodes([])
      setEdges([])
      setWorkflowName('New Blank Workflow')
      setWorkflowId(`wf_${Date.now()}`)
      setSelectedDropdownKey('template:blank')
    }
  }

  const handleDropdownChange = (value: string) => {
    if (value.startsWith('saved:')) {
      const wfId = value.replace('saved:', '')
      loadSavedWorkflow(wfId)
    } else if (value.startsWith('template:')) {
      const tpl = value.replace('template:', '')
      loadTemplate(tpl)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', width: '100vw', height: '100vh', overflow: 'hidden' }}>
      {/* Top Navbar */}
      <header
        style={{
          height: 52,
          backgroundColor: '#0f172a',
          borderBottom: '1px solid #334155',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 16px',
          zIndex: 30,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '4px 8px',
              borderRadius: 6,
              backgroundColor: '#1e293b',
              border: '1px solid #334155',
            }}
          >
            <Zap size={18} color="#38bdf8" />
            <span style={{ fontSize: 14, fontWeight: 800, color: '#f8fafc', letterSpacing: '-0.02em' }}>
              OS RPA STUDIO
            </span>
          </div>

          <input
            type="text"
            value={workflowName}
            onChange={(e) => setWorkflowName(e.target.value)}
            style={{
              backgroundColor: 'transparent',
              border: '1px solid transparent',
              borderRadius: 4,
              color: '#f8fafc',
              fontSize: 13,
              fontWeight: 600,
              padding: '4px 8px',
              outline: 'none',
              width: 260,
            }}
            onFocus={(e) => (e.target.style.borderColor = '#38bdf8')}
            onBlur={(e) => (e.target.style.borderColor = 'transparent')}
          />
        </div>

        {/* Action Controls & Debugger Toolbar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {/* Workflows & Templates Dropdown */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <FolderOpen size={15} color="#38bdf8" />
            <select
              value={selectedDropdownKey}
              onChange={(e) => handleDropdownChange(e.target.value)}
              style={{
                backgroundColor: '#1e293b',
                border: '1px solid #334155',
                color: '#cbd5e1',
                fontSize: 12,
                fontWeight: 500,
                padding: '6px 10px',
                borderRadius: 6,
                outline: 'none',
                cursor: 'pointer',
                maxWidth: 220,
              }}
            >
              {savedWorkflows.length > 0 && (
                <optgroup label="Saved Workflows">
                  {savedWorkflows.map((wf) => (
                    <option key={wf.id} value={`saved:${wf.id}`}>
                      {wf.name}
                    </option>
                  ))}
                </optgroup>
              )}
              <optgroup label="Starter Templates">
                <option value="template:queue_excel">Template: Queue + Script + Excel</option>
                <option value="template:web_automation">Template: Web Browser Scraper</option>
                <option value="template:blank">Blank Canvas</option>
              </optgroup>
            </select>
          </div>

          {/* Slow-Motion Execution Slider */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              backgroundColor: '#1e293b',
              padding: '4px 8px',
              borderRadius: 6,
              border: '1px solid #334155',
            }}
            title="Slow-motion delay between step executions"
          >
            <Gauge size={13} color="#94a3b8" />
            <span style={{ fontSize: 11, color: '#94a3b8' }}>{stepDelay}ms</span>
            <input
              type="range"
              min={0}
              max={2000}
              step={100}
              value={stepDelay}
              onChange={(e) => handleStepDelayChange(Number(e.target.value))}
              style={{ width: 70, cursor: 'pointer', accentColor: '#38bdf8' }}
            />
          </div>

          {/* Work Queues Modal */}
          <button
            onClick={() => setIsQueueModalOpen(true)}
            style={{
              backgroundColor: '#1e293b',
              border: '1px solid #334155',
              color: '#f59e0b',
              borderRadius: 6,
              padding: '6px 10px',
              fontSize: 12,
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 5,
            }}
          >
            <Inbox size={13} /> Queues
          </button>

          {/* Save Workflow Button */}
          <button
            onClick={handleSaveWorkflow}
            style={{
              backgroundColor: '#1e293b',
              border: '1px solid #334155',
              color: '#34d399',
              borderRadius: 6,
              padding: '6px 10px',
              fontSize: 12,
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 5,
            }}
          >
            <Save size={13} /> Save
          </button>

          {/* Divider */}
          <div style={{ width: 1, height: 24, backgroundColor: '#334155' }} />

          {/* Debug / Resume (F5) Button */}
          <button
            onClick={handleStartDebug}
            style={{
              backgroundColor: isPaused ? '#f59e0b' : '#7c3aed',
              border: 'none',
              color: '#ffffff',
              borderRadius: 6,
              padding: '6px 12px',
              fontSize: 12,
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              boxShadow: isPaused ? '0 0 10px #f59e0b' : '0 2px 6px rgba(124, 58, 237, 0.4)',
            }}
            title={isPaused ? 'Resume execution (F5)' : 'Start Interactive Debugging (F5)'}
          >
            {isPaused ? <Play size={13} fill="#ffffff" /> : <Bug size={13} />}
            {isPaused ? 'Resume (F5)' : isDebugging ? 'Debugging...' : 'Debug (F5)'}
          </button>

          {/* Step Over (F10) Button */}
          {isDebugging && (
            <button
              onClick={handleStepOver}
              disabled={!isPaused}
              style={{
                backgroundColor: isPaused ? '#1e293b' : '#0f172a',
                border: '1px solid #334155',
                color: isPaused ? '#38bdf8' : '#64748b',
                borderRadius: 6,
                padding: '6px 10px',
                fontSize: 12,
                fontWeight: 600,
                cursor: isPaused ? 'pointer' : 'not-allowed',
                display: 'flex',
                alignItems: 'center',
                gap: 5,
              }}
              title="Step Over Next Node (F10)"
            >
              <SkipForward size={13} /> Step (F10)
            </button>
          )}

          {/* Pause Button */}
          {isRunning && isDebugging && !isPaused && (
            <button
              onClick={handlePause}
              style={{
                backgroundColor: '#1e293b',
                border: '1px solid #334155',
                color: '#f59e0b',
                borderRadius: 6,
                padding: '6px 10px',
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 5,
              }}
              title="Pause execution"
            >
              <Pause size={13} /> Pause
            </button>
          )}

          {/* Stop Button */}
          {isRunning && (
            <button
              onClick={handleStop}
              style={{
                backgroundColor: '#ef4444',
                border: 'none',
                color: '#ffffff',
                borderRadius: 6,
                padding: '6px 10px',
                fontSize: 12,
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 5,
              }}
              title="Stop workflow immediately"
            >
              <Square size={12} fill="#ffffff" /> Stop
            </button>
          )}

          {/* Run Robot (Full Speed) Button */}
          {!isDebugging && (
            <button
              onClick={handleRunWorkflow}
              disabled={isRunning}
              style={{
                backgroundColor: isRunning ? '#0284c7' : '#0284c7',
                border: 'none',
                color: '#ffffff',
                borderRadius: 6,
                padding: '6px 14px',
                fontSize: 12,
                fontWeight: 700,
                cursor: isRunning ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                boxShadow: '0 2px 8px rgba(2, 132, 199, 0.4)',
              }}
            >
              <Play size={13} fill="#ffffff" /> {isRunning ? 'Running...' : 'Run Robot'}
            </button>
          )}
        </div>
      </header>

      {/* Main Workspace (3 columns + bottom console) */}
      <div style={{ display: 'flex', flex: 1, position: 'relative', overflow: 'hidden' }}>
        {/* Left: Action Palette */}
        <ActionPalette actions={actions} onAddNode={handleAddNode} />

        {/* Center: React Flow Canvas */}
        <div style={{ flex: 1, height: '100%', position: 'relative' }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={(_, node) => setSelectedNodeId(node.id)}
            onPaneClick={() => setSelectedNodeId(null)}
            nodeTypes={nodeTypes}
            fitView
          >
            <Background color="#334155" gap={18} size={1} />
            <Controls />
            <MiniMap
              nodeColor={(node) => {
                const cat = (node.data as any)?.type || ''
                if (cat.startsWith('flow')) return '#c084fc'
                if (cat.startsWith('http')) return '#2dd4bf'
                if (cat.startsWith('file')) return '#fb923c'
                if (cat.startsWith('queue')) return '#f59e0b'
                if (cat.startsWith('web')) return '#38bdf8'
                if (cat.startsWith('desktop')) return '#e879f9'
                if (cat.startsWith('excel')) return '#34d399'
                if (cat.startsWith('script')) return '#a78bfa'
                return '#94a3b8'
              }}
              style={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: 6 }}
            />
          </ReactFlow>

          {/* Bottom Execution Console Drawer with Live Variables & Call Stack */}
          <ConsolePanel
            logs={logs}
            variables={liveVariables}
            stepHistory={stepHistory}
            bots={bots}
            isOpen={isConsoleOpen}
            onToggle={() => setIsConsoleOpen(!isConsoleOpen)}
            onClear={() => setLogs([])}
            isRunning={isRunning}
            isPaused={isPaused}
            duration={executionDuration}
            onRefreshBots={fetchBots}
            onTriggerOnBot={handleTriggerOnBot}
          />
        </div>

        {/* Right: Properties & Monaco Code Editor */}
        <PropertiesPanel
          selectedNode={selectedNode}
          actionDef={selectedActionDef}
          onUpdateParams={handleUpdateParams}
          onUpdateMetadata={handleUpdateMetadata}
        />
      </div>

      {/* Queue Management Modal */}
      <QueueModal isOpen={isQueueModalOpen} onClose={() => setIsQueueModalOpen(false)} />
    </div>
  )
}
export default App
