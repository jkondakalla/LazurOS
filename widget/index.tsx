import React, { useState, useEffect } from 'react'

export interface LazurosWidgetProps {
  apiUrl?: string
}

type NodeStatus = 'unknown' | 'awake' | 'sleeping'

export default function LazurosWidget({ apiUrl = 'http://localhost:8080' }: LazurosWidgetProps) {
  const [status, setStatus] = useState<NodeStatus>('unknown')
  const [waking, setWaking] = useState(false)

  const checkStatus = async () => {
    try {
      const r = await fetch(`${apiUrl}/health`, {
        signal: AbortSignal.timeout(3000),
      })
      if (r.ok) {
        const data = await r.json()
        setStatus(data.compute_online ? 'awake' : 'sleeping')
      } else {
        setStatus('sleeping')
      }
    } catch {
      setStatus('sleeping')
    }
  }

  useEffect(() => {
    checkStatus()
    const id = setInterval(checkStatus, 30000)
    return () => clearInterval(id)
  }, [apiUrl])

  const handleWake = async () => {
    setWaking(true)
    try {
      await fetch(`${apiUrl}/wake`, { method: 'POST' })
      setTimeout(checkStatus, 5000)
    } catch (e) {
      console.error('Wake failed:', e)
    } finally {
      setWaking(false)
    }
  }

  const COLOR = '#4ecdc4'
  const statusColor =
    status === 'awake'    ? '#5cd66a' :
    status === 'sleeping' ? '#e5a00d' : '#6b7280'
  const statusLabel =
    status === 'awake'    ? 'ONLINE' :
    status === 'sleeping' ? 'SLEEPING' : 'SCANNING…'

  return (
    <div style={{
      height: '100%',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      gap: 14, padding: 24, textAlign: 'center',
      fontFamily: 'var(--hub-font-mono, monospace)',
      background: 'var(--hub-bg-0, #0a0a0f)',
    }}>
      <div style={{
        fontSize: 30, color: COLOR,
        filter: `drop-shadow(0 0 10px ${COLOR}88)`,
        lineHeight: 1,
      }}>⊛</div>

      <div style={{ fontSize: 14, letterSpacing: '0.15em', color: COLOR, fontWeight: 600 }}>
        LAZUROS
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{
          width: 7, height: 7, borderRadius: '50%',
          background: statusColor,
          boxShadow: `0 0 6px ${statusColor}`,
          animation: status === 'unknown' ? 'pulse 1.4s ease-in-out infinite' : 'none',
        }} />
        <span style={{ fontSize: 9, letterSpacing: '0.18em', color: statusColor }}>
          {statusLabel}
        </span>
      </div>

      {status !== 'awake' && (
        <button
          onClick={handleWake}
          disabled={waking}
          style={{
            background: 'transparent',
            border: `1px solid ${COLOR}55`,
            color: waking ? `${COLOR}88` : COLOR,
            fontFamily: 'var(--hub-font-mono, monospace)',
            fontSize: 9,
            letterSpacing: '0.15em',
            padding: '6px 18px',
            cursor: waking ? 'wait' : 'pointer',
            transition: 'border-color 0.15s, color 0.15s',
          }}
        >
          {waking ? 'WAKING…' : 'WAKE NODE →'}
        </button>
      )}

      <div style={{
        fontSize: 9, letterSpacing: '0.1em',
        padding: '2px 8px',
        border: `1px solid ${COLOR}28`,
        color: 'var(--hub-cream-dim, #555)',
        marginTop: 4,
      }}>
        RMT-002 // COMPUTE PROXY
      </div>
    </div>
  )
}
