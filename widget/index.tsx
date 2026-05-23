import React, { useState, useEffect, useCallback } from 'react'

export interface LazurosWidgetProps {
  apiUrl?: string
}

interface OllamaModel {
  name: string
  size: number
  digest: string
  details?: { parameter_size?: string; family?: string }
}

interface NodeState {
  online: boolean
  checking: boolean
  computeIp: string
}

interface ModelsState {
  available: OllamaModel[]
  running: string[]  // names of models loaded in VRAM
  loaded: boolean
}

function fmtSize(bytes: number): string {
  const gb = bytes / 1_073_741_824
  return gb >= 1 ? `${gb.toFixed(1)}G` : `${(bytes / 1_048_576).toFixed(0)}M`
}

const ACCENT = '#4ecdc4'

export default function LazurosWidget({ apiUrl = '/api/lazuros' }: LazurosWidgetProps) {
  const base = apiUrl.replace(/\/$/, '')

  const [node, setNode]     = useState<NodeState>({ online: false, checking: true, computeIp: '' })
  const [models, setModels] = useState<ModelsState>({ available: [], running: [], loaded: false })
  const [waking, setWaking] = useState(false)
  const [copied, setCopied] = useState(false)

  const checkHealth = useCallback(async () => {
    try {
      const r    = await fetch(`${base}/health`, { signal: AbortSignal.timeout(3000) })
      const data = await r.json()
      setNode({ online: !!data.compute_online, checking: false, computeIp: data.compute_ip || '' })
      return !!data.compute_online
    } catch {
      setNode(prev => ({ ...prev, online: false, checking: false }))
      return false
    }
  }, [base])

  const loadModels = useCallback(async () => {
    try {
      const [avail, ps] = await Promise.all([
        fetch(`${base}/models`, { credentials: 'include' }).then(r => r.json()),
        fetch(`${base}/ps`,     { credentials: 'include' }).then(r => r.json()),
      ])
      setModels({
        available: avail.models || [],
        running:   (ps.models || []).map((m: OllamaModel) => m.name),
        loaded:    true,
      })
    } catch {
      setModels(prev => ({ ...prev, loaded: true }))
    }
  }, [base])

  useEffect(() => {
    let cancelled = false

    const poll = async () => {
      const alive = await checkHealth()
      if (!cancelled && alive) loadModels()
    }

    poll()
    const id = setInterval(() => { if (!cancelled) poll() }, 30_000)
    return () => { cancelled = true; clearInterval(id) }
  }, [checkHealth, loadModels])

  const handleWake = async () => {
    setWaking(true)
    try {
      await fetch(`${base}/wake`, { method: 'POST', credentials: 'include' })
      // Poll until the node comes up (up to 60s, checking every 2s)
      for (let i = 0; i < 30; i++) {
        await new Promise(r => setTimeout(r, 2000))
        const alive = await checkHealth()
        if (alive) { await loadModels(); break }
      }
    } finally {
      setWaking(false)
    }
  }

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(base)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch { /* ignore */ }
  }

  const nodeColor = node.checking ? '#6b7280'
    : node.online               ? '#5cd66a'
    : '#e5a00d'

  const nodeLabel = node.checking ? 'SCANNING…'
    : node.online               ? 'ONLINE'
    : 'SLEEPING'

  return (
    <div style={{
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      fontFamily: 'var(--hub-font-mono, "Courier New", monospace)',
      background: 'var(--hub-bg-0, #0a0a0f)',
      color: 'var(--hub-cream, #d4cfc5)',
      overflow: 'hidden',
    }}>
      {/* ── Header ─────────────────────────────────────────────────── */}
      <div style={{
        display: 'flex', alignItems: 'center',
        padding: '8px 12px',
        borderBottom: `1px solid ${ACCENT}22`,
        gap: 10, flexShrink: 0,
      }}>
        <span style={{
          fontSize: 16, color: ACCENT,
          filter: `drop-shadow(0 0 6px ${ACCENT}88)`,
          lineHeight: 1,
        }}>⊛</span>

        <span style={{
          fontSize: 11, letterSpacing: '0.2em',
          fontWeight: 700, color: ACCENT,
          textShadow: `0 0 8px ${ACCENT}66`,
        }}>LAZUROS</span>

        <div style={{ flex: 1 }} />

        {/* Status LED */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{
            width: 7, height: 7, borderRadius: '50%',
            background: nodeColor,
            boxShadow: `0 0 6px ${nodeColor}`,
            animation: node.checking ? 'pulse 1.4s ease-in-out infinite' : 'none',
          }} />
          <span style={{ fontSize: 8, letterSpacing: '0.2em', color: nodeColor }}>
            {nodeLabel}
          </span>
        </div>
      </div>

      {/* ── Node info row ───────────────────────────────────────────── */}
      <div style={{
        padding: '5px 12px',
        fontSize: 8, letterSpacing: '0.14em',
        color: 'var(--hub-cream-faint, #555)',
        borderBottom: `1px solid ${ACCENT}18`,
        flexShrink: 0,
      }}>
        COMPUTE NODE · {node.computeIp || 'NOT CONFIGURED'} · OLLAMA
      </div>

      {/* ── Body ────────────────────────────────────────────────────── */}
      <div style={{ flex: 1, overflow: 'auto', padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 10 }}>

        {/* Wake button — when sleeping */}
        {!node.online && !node.checking && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'center', padding: '12px 0' }}>
            <span style={{ fontSize: 8, letterSpacing: '0.15em', color: '#e5a00d55' }}>
              NODE IS SLEEPING
            </span>
            <button
              onClick={handleWake}
              disabled={waking}
              style={{
                background: 'transparent',
                border: `1px solid ${ACCENT}55`,
                color: waking ? `${ACCENT}55` : ACCENT,
                fontFamily: 'var(--hub-font-mono, monospace)',
                fontSize: 9, letterSpacing: '0.18em',
                padding: '7px 20px',
                cursor: waking ? 'wait' : 'pointer',
                transition: 'all 0.15s',
              }}
              onMouseEnter={e => { if (!waking) { (e.currentTarget as HTMLElement).style.borderColor = ACCENT; } }}
              onMouseLeave={e => { if (!waking) { (e.currentTarget as HTMLElement).style.borderColor = ACCENT + '55'; } }}
            >
              {waking ? '⌛ WAKING NODE…' : '⏻ WAKE NODE →'}
            </button>
            {waking && (
              <span style={{ fontSize: 7, letterSpacing: '0.1em', color: '#6b7280' }}>
                WAITING FOR BOOT · UP TO {45}s
              </span>
            )}
          </div>
        )}

        {/* Models list — when online */}
        {node.online && (
          <>
            <Section label="MODELS" accent={ACCENT}>
              {!models.loaded ? (
                <Row dim>LOADING…</Row>
              ) : models.available.length === 0 ? (
                <Row dim>NO MODELS PULLED — run: ollama pull llama3.2</Row>
              ) : (
                models.available.map(m => {
                  const isRunning = models.running.includes(m.name)
                  const params    = m.details?.parameter_size
                  return (
                    <div key={m.name} style={{
                      display: 'flex', alignItems: 'center', gap: 8,
                      padding: '4px 8px',
                      background: isRunning ? `${ACCENT}0d` : 'transparent',
                      border: `1px solid ${isRunning ? ACCENT + '33' : 'transparent'}`,
                      transition: 'all 0.12s',
                    }}>
                      {/* Running indicator */}
                      <div style={{
                        width: 5, height: 5, borderRadius: '50%', flexShrink: 0,
                        background: isRunning ? '#5cd66a' : '#6b728055',
                        boxShadow: isRunning ? '0 0 5px #5cd66a' : 'none',
                      }} />

                      <span style={{
                        flex: 1,
                        fontSize: 9, letterSpacing: '0.1em',
                        color: isRunning ? ACCENT : 'var(--hub-cream, #d4cfc5)',
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      }}>
                        {m.name}
                      </span>

                      <span style={{ fontSize: 7.5, letterSpacing: '0.08em', color: '#6b7280', flexShrink: 0 }}>
                        {params || fmtSize(m.size)}
                      </span>

                      {isRunning && (
                        <span style={{
                          fontSize: 6.5, letterSpacing: '0.1em', padding: '1px 5px',
                          background: '#5cd66a22', border: '1px solid #5cd66a44',
                          color: '#5cd66a', flexShrink: 0,
                        }}>LOADED</span>
                      )}
                    </div>
                  )
                })
              )}
            </Section>
          </>
        )}

        {/* API Endpoint */}
        <Section label="API ENDPOINT" accent={ACCENT}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '5px 8px',
            background: 'var(--hub-bg-2, #11100d)',
            border: `1px solid ${ACCENT}22`,
          }}>
            <span style={{
              flex: 1, fontSize: 8.5, letterSpacing: '0.08em',
              color: ACCENT, fontFamily: 'monospace',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {base}/api/chat
            </span>
            <button
              onClick={handleCopy}
              style={{
                background: 'transparent',
                border: `1px solid ${ACCENT}33`,
                color: copied ? '#5cd66a' : ACCENT,
                fontFamily: 'var(--hub-font-mono, monospace)',
                fontSize: 7.5, letterSpacing: '0.12em',
                padding: '3px 8px', cursor: 'pointer',
                transition: 'color 0.15s',
                flexShrink: 0,
              }}
            >
              {copied ? '✓ COPIED' : 'COPY'}
            </button>
          </div>
          <div style={{ fontSize: 7, letterSpacing: '0.1em', color: '#6b7280', padding: '3px 8px 0' }}>
            BEARER TOKEN REQUIRED · OPENAI-COMPATIBLE
          </div>
        </Section>
      </div>

      {/* ── Footer ──────────────────────────────────────────────────── */}
      <div style={{
        padding: '5px 12px',
        borderTop: `1px solid ${ACCENT}18`,
        fontSize: 7.5, letterSpacing: '0.12em',
        color: '#6b7280', flexShrink: 0,
        display: 'flex', justifyContent: 'space-between',
      }}>
        <span>RMT-002 // COMPUTE PROXY</span>
        <span style={{ color: node.online ? '#5cd66a' : '#6b7280' }}>
          {node.online && models.loaded ? `${models.available.length} MODEL${models.available.length !== 1 ? 'S' : ''}` : '—'}
        </span>
      </div>
    </div>
  )
}

function Section({ label, accent, children }: { label: string; accent: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <div style={{
        fontSize: 7.5, letterSpacing: '0.22em', fontWeight: 700,
        color: accent + 'aa',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        {label}
        <span style={{ flex: 1, height: 1, background: accent + '22' }} />
      </div>
      {children}
    </div>
  )
}

function Row({ children, dim }: { children: React.ReactNode; dim?: boolean }) {
  return (
    <div style={{
      padding: '4px 8px',
      fontSize: 8.5,
      letterSpacing: '0.1em',
      color: dim ? '#6b7280' : 'var(--hub-cream, #d4cfc5)',
    }}>
      {children}
    </div>
  )
}
