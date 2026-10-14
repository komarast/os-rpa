import React, { useState } from 'react'
import { BaseEdge, EdgeLabelRenderer, getBezierPath, useReactFlow } from '@xyflow/react'
import type { EdgeProps } from '@xyflow/react'
import { X } from 'lucide-react'

/** Default edge with a one-click remove button at its midpoint, shown on hover or when selected. */
export const DeletableEdge: React.FC<EdgeProps> = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style,
  markerEnd,
  selected,
}) => {
  const { deleteElements } = useReactFlow()
  const [hovered, setHovered] = useState(false)
  const [path, labelX, labelY] = getBezierPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition })
  const visible = hovered || selected

  return (
    <>
      <BaseEdge id={id} path={path} style={style} markerEnd={markerEnd} />
      {/* Wide invisible hit area so the thin line is easy to hover */}
      <path
        d={path}
        fill="none"
        stroke="transparent"
        strokeWidth={20}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      />
      <EdgeLabelRenderer>
        <button
          className="nodrag nopan"
          onClick={(e) => {
            e.stopPropagation()
            deleteElements({ edges: [{ id }] })
          }}
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
          title="Remove connection"
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
            pointerEvents: visible ? 'all' : 'none',
            opacity: visible ? 1 : 0,
            transition: 'opacity 0.12s ease',
            width: 20,
            height: 20,
            borderRadius: '50%',
            border: '1px solid #475569',
            backgroundColor: '#1e293b',
            color: '#f43f5e',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 0,
            cursor: 'pointer',
            boxShadow: '0 2px 6px rgba(0,0,0,0.4)',
          }}
        >
          <X size={12} />
        </button>
      </EdgeLabelRenderer>
    </>
  )
}
