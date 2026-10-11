import React, { useState, useEffect } from 'react'
import {
  X,
  Inbox,
  RotateCw,
  Plus,
  Trash2,
  CheckCircle2,
  Clock,
  AlertCircle,
  PlayCircle,
} from 'lucide-react'
import type { QueueSummary, QueueItem } from '../types'

interface QueueModalProps {
  isOpen: boolean
  onClose: () => void
}

export const QueueModal: React.FC<QueueModalProps> = ({ isOpen, onClose }) => {
  const [queues, setQueues] = useState<QueueSummary[]>([])
  const [selectedQueue, setSelectedQueue] = useState<string>('')
  const [items, setItems] = useState<QueueItem[]>([])
  const [loading, setLoading] = useState(false)
  const [showAddForm, setShowAddForm] = useState(false)
  const [newItemQueue, setNewItemQueue] = useState('CustomerQueue')
  const [newItemPayload, setNewItemPayload] = useState('{\n  "account_id": "ACC-101",\n  "action": "verify",\n  "amount": 250.0\n}')
  const [newItemPriority, setNewItemPriority] = useState(0)

  const fetchQueues = async () => {
    try {
      const res = await fetch('/api/queues')
      if (res.ok) {
        const data = await res.json()
        setQueues(data)
        if (data.length > 0 && !selectedQueue) {
          setSelectedQueue(data[0].queue_name)
        }
      }
    } catch (e) {
      console.error(e)
    }
  }

  const fetchItems = async (queueName: string) => {
    if (!queueName) return
    setLoading(true)
    try {
      const res = await fetch(`/api/queues/${encodeURIComponent(queueName)}/items`)
      if (res.ok) {
        const data = await res.json()
        setItems(data)
      }
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (isOpen) {
      fetchQueues()
    }
  }, [isOpen])

  useEffect(() => {
    if (selectedQueue) {
      fetchItems(selectedQueue)
    }
  }, [selectedQueue])

  const handleAddItem = async () => {
    try {
      const parsed = JSON.parse(newItemPayload)
      const res = await fetch('/api/queues/items', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          queue_name: newItemQueue,
          payload: parsed,
          priority: newItemPriority,
        }),
      })
      if (res.ok) {
        setShowAddForm(false)
        fetchQueues()
        setSelectedQueue(newItemQueue)
        fetchItems(newItemQueue)
      }
    } catch (e) {
      alert('Invalid JSON in payload: ' + e)
    }
  }

  const handleRetry = async (itemId: string) => {
    try {
      const res = await fetch(`/api/queues/items/${itemId}/retry`, { method: 'POST' })
      if (res.ok) {
        fetchItems(selectedQueue)
        fetchQueues()
      }
    } catch (e) {
      console.error(e)
    }
  }

  const handleDelete = async (itemId: string) => {
    try {
      const res = await fetch(`/api/queues/items/${itemId}`, { method: 'DELETE' })
      if (res.ok) {
        fetchItems(selectedQueue)
        fetchQueues()
      }
    } catch (e) {
      console.error(e)
    }
  }

  if (!isOpen) return null

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'NEW':
        return (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: '#38bdf8', backgroundColor: '#075985', padding: '2px 6px', borderRadius: 4, fontSize: 11 }}>
            <Clock size={12} /> NEW
          </span>
        )
      case 'IN_PROGRESS':
        return (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: '#f59e0b', backgroundColor: '#78350f', padding: '2px 6px', borderRadius: 4, fontSize: 11 }}>
            <PlayCircle size={12} /> IN PROGRESS
          </span>
        )
      case 'SUCCESS':
        return (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: '#34d399', backgroundColor: '#064e3b', padding: '2px 6px', borderRadius: 4, fontSize: 11 }}>
            <CheckCircle2 size={12} /> SUCCESS
          </span>
        )
      case 'FAILED':
      default:
        return (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: '#f43f5e', backgroundColor: '#881337', padding: '2px 6px', borderRadius: 4, fontSize: 11 }}>
            <AlertCircle size={12} /> FAILED
          </span>
        )
    }
  }

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
          maxWidth: 950,
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
            <div style={{ backgroundColor: '#f59e0b', color: '#0f172a', padding: 6, borderRadius: 6, display: 'flex' }}>
              <Inbox size={18} />
            </div>
            <div>
              <div style={{ fontSize: 16, fontWeight: 700, color: '#f8fafc' }}>RPA Work Queues</div>
              <div style={{ fontSize: 12, color: '#94a3b8' }}>Inspect transaction items, payload data, and status history</div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button
              onClick={() => {
                fetchQueues()
                if (selectedQueue) fetchItems(selectedQueue)
              }}
              style={{
                backgroundColor: '#1e293b',
                border: '1px solid #334155',
                color: '#94a3b8',
                borderRadius: 6,
                padding: '6px 10px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                fontSize: 12,
              }}
            >
              <RotateCw size={14} /> Refresh
            </button>
            <button
              onClick={() => setShowAddForm(true)}
              style={{
                backgroundColor: '#38bdf8',
                border: 'none',
                color: '#0f172a',
                borderRadius: 6,
                padding: '6px 12px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                fontSize: 12,
                fontWeight: 600,
              }}
            >
              <Plus size={14} /> Add Item
            </button>
            <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: 4 }}>
              <X size={20} />
            </button>
          </div>
        </div>

        {/* Content Area */}
        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
          {/* Queues List */}
          <div style={{ width: 240, borderRight: '1px solid #334155', padding: 12, overflowY: 'auto' }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#94a3b8', marginBottom: 8, letterSpacing: '0.05em' }}>
              QUEUES
            </div>
            {queues.length === 0 ? (
              <div style={{ fontSize: 12, color: '#64748b', padding: 8 }}>No active queues found</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {queues.map((q) => {
                  const active = selectedQueue === q.queue_name
                  return (
                    <div
                      key={q.queue_name}
                      onClick={() => setSelectedQueue(q.queue_name)}
                      style={{
                        padding: '8px 10px',
                        borderRadius: 6,
                        backgroundColor: active ? '#1e293b' : 'transparent',
                        border: active ? '1px solid #38bdf8' : '1px solid transparent',
                        cursor: 'pointer',
                      }}
                    >
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#f8fafc' }}>{q.queue_name}</div>
                      <div style={{ display: 'flex', gap: 6, marginTop: 4, fontSize: 10 }}>
                        <span style={{ color: '#38bdf8' }}>New: {q.new_items}</span>
                        <span style={{ color: '#34d399' }}>Done: {q.success_items}</span>
                        {q.failed_items > 0 && <span style={{ color: '#f43f5e' }}>Failed: {q.failed_items}</span>}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* Items Table */}
          <div style={{ flex: 1, padding: 16, overflowY: 'auto' }}>
            {selectedQueue ? (
              <>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#f8fafc', marginBottom: 12 }}>
                  Queue: <span style={{ color: '#38bdf8' }}>{selectedQueue}</span> ({items.length} items)
                </div>
                {loading ? (
                  <div style={{ color: '#94a3b8', fontSize: 13 }}>Loading queue items...</div>
                ) : items.length === 0 ? (
                  <div style={{ color: '#64748b', fontSize: 13 }}>No items in this queue yet.</div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {items.map((item) => (
                      <div
                        key={item.id}
                        style={{
                          backgroundColor: '#1e293b',
                          border: '1px solid #334155',
                          borderRadius: 8,
                          padding: '10px 14px',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 6,
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            {getStatusBadge(item.status)}
                            <span style={{ fontSize: 11, color: '#64748b', fontFamily: 'monospace' }}>
                              {item.id.slice(0, 8)}...
                            </span>
                            <span style={{ fontSize: 11, color: '#94a3b8' }}>
                              Priority: {item.priority} | Retries: {item.retry_count}/{item.max_retries}
                            </span>
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            {item.status === 'FAILED' && (
                              <button
                                onClick={() => handleRetry(item.id)}
                                style={{
                                  background: 'none',
                                  border: '1px solid #38bdf8',
                                  color: '#38bdf8',
                                  borderRadius: 4,
                                  padding: '2px 6px',
                                  fontSize: 10,
                                  cursor: 'pointer',
                                }}
                              >
                                Retry
                              </button>
                            )}
                            <button
                              onClick={() => handleDelete(item.id)}
                              style={{
                                background: 'none',
                                border: 'none',
                                color: '#64748b',
                                cursor: 'pointer',
                                padding: 2,
                              }}
                              title="Delete item"
                            >
                              <Trash2 size={13} />
                            </button>
                          </div>
                        </div>

                        <div style={{ fontSize: 11, backgroundColor: '#0f172a', padding: 6, borderRadius: 4, fontFamily: 'monospace', color: '#cbd5e1' }}>
                          Payload: {JSON.stringify(item.payload)}
                        </div>

                        {item.output_data && (
                          <div style={{ fontSize: 11, backgroundColor: '#0f172a', padding: 6, borderRadius: 4, fontFamily: 'monospace', color: '#34d399' }}>
                            Output: {JSON.stringify(item.output_data)}
                          </div>
                        )}

                        {item.error_message && (
                          <div style={{ fontSize: 11, color: '#f43f5e' }}>
                            Error: {item.error_message}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <div style={{ color: '#64748b', fontSize: 13 }}>Select a queue on the left</div>
            )}
          </div>
        </div>

        {/* Add Item Modal Overlay */}
        {showAddForm && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              backgroundColor: 'rgba(0,0,0,0.8)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              zIndex: 60,
            }}
          >
            <div
              style={{
                width: 440,
                backgroundColor: '#1e293b',
                border: '1px solid #334155',
                borderRadius: 8,
                padding: 16,
                display: 'flex',
                flexDirection: 'column',
                gap: 12,
              }}
            >
              <div style={{ fontSize: 14, fontWeight: 700, color: '#f8fafc' }}>Enqueue New RPA Item</div>

              <div>
                <label style={{ fontSize: 11, color: '#94a3b8', display: 'block', marginBottom: 4 }}>Queue Name</label>
                <input
                  type="text"
                  value={newItemQueue}
                  onChange={(e) => setNewItemQueue(e.target.value)}
                  style={{ width: '100%', backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: 4, padding: 6, color: '#fff', fontSize: 12 }}
                />
              </div>

              <div>
                <label style={{ fontSize: 11, color: '#94a3b8', display: 'block', marginBottom: 4 }}>Priority (0 = Normal, 10 = High)</label>
                <input
                  type="number"
                  value={newItemPriority}
                  onChange={(e) => setNewItemPriority(Number(e.target.value))}
                  style={{ width: '100%', backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: 4, padding: 6, color: '#fff', fontSize: 12 }}
                />
              </div>

              <div>
                <label style={{ fontSize: 11, color: '#94a3b8', display: 'block', marginBottom: 4 }}>Item Payload (JSON)</label>
                <textarea
                  rows={5}
                  value={newItemPayload}
                  onChange={(e) => setNewItemPayload(e.target.value)}
                  style={{ width: '100%', backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: 4, padding: 6, color: '#38bdf8', fontSize: 12, fontFamily: 'monospace' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 4 }}>
                <button
                  onClick={() => setShowAddForm(false)}
                  style={{ backgroundColor: 'transparent', border: '1px solid #334155', color: '#94a3b8', padding: '6px 12px', borderRadius: 4, cursor: 'pointer', fontSize: 12 }}
                >
                  Cancel
                </button>
                <button
                  onClick={handleAddItem}
                  style={{ backgroundColor: '#38bdf8', border: 'none', color: '#0f172a', padding: '6px 14px', borderRadius: 4, fontWeight: 600, cursor: 'pointer', fontSize: 12 }}
                >
                  Enqueue Item
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

