import { useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import SplineScene from '../components/SplineScene'

export default function UploadPage() {
  const [isDragging, setIsDragging] = useState(false)
  const [fileQueue, setFileQueue] = useState([])
  const splineRef = useRef(null)
  const fileInputRef = useRef(null)
  const navigate = useNavigate()

  const handleSplineLoad = (splineApp) => {
    splineRef.current = splineApp
    // Zoom way out so the robot is not cut off
    const zoom = window.innerHeight < 850 ? 0.35 : 0.45;
    try { splineApp.setZoom(zoom) } catch (e) { }
  }

  const onDragEnter = useCallback((e) => {
    e.preventDefault(); setIsDragging(true)
    try { splineRef.current?.emitEvent('mouseDown', 'Head') } catch (_) { }
  }, [])

  const onDragLeave = useCallback((e) => {
    e.preventDefault(); setIsDragging(false)
    try { splineRef.current?.emitEvent('mouseUp', 'Head') } catch (_) { }
  }, [])

  const onDragOver = useCallback((e) => { e.preventDefault() }, [])

  const handleFiles = (files) => {
    if (!files?.length) return
    const incoming = Array.from(files)
    if (fileQueue.length + incoming.length > 20) {
      toast.error('Limit: Max 20 files per batch')
      const spaceLeft = 20 - fileQueue.length
      if (spaceLeft > 0) {
        setFileQueue(prev => [...prev, ...incoming.slice(0, spaceLeft)])
      }
    } else {
      setFileQueue(prev => [...prev, ...incoming])
    }
    try { splineRef.current?.emitEvent('keyDown', 'Head') } catch (_) { }
  }

  const removeFile = (index) => {
    setFileQueue(prev => prev.filter((_, i) => i !== index))
    try { splineRef.current?.emitEvent('keyUp', 'Head') } catch (_) { }
  }

  const onDrop = useCallback((e) => {
    e.preventDefault(); setIsDragging(false)
    try { splineRef.current?.emitEvent('mouseUp', 'Head') } catch (_) { }
    handleFiles(e.dataTransfer.files)
  }, [])

  const submitBatch = () => {
    if (fileQueue.length > 0) {
      navigate('/send', { state: { queue: fileQueue } })
    }
  }

  const handleMouseMove = (e) => {
    const card = e.currentTarget
    const rect = card.getBoundingClientRect()
    const x = ((e.clientX - rect.left) / rect.width) * 100
    const y = ((e.clientY - rect.top) / rect.height) * 100
    card.style.setProperty('--mouse-x', `${x}%`)
    card.style.setProperty('--mouse-y', `${y}%`)
  }

  return (
    <div className="upload-outer">
      <div className="center-spotlight" aria-hidden="true" />
      <div className="edge-vignette edge-vignette--right" aria-hidden="true" />
      <div className="edge-vignette edge-vignette--left" aria-hidden="true" />

      {/* 3D HERO - Floating Background */}
      <div className="hero-visual-wrapper" style={{ position: 'absolute', top: '-15vh', left: 0, width: '100%', height: '100vh', zIndex: 0 }}>
        <div className="spline-stage">
          <SplineScene
            scene="https://prod.spline.design/SxenySvtEVPgRumV/scene.splinecode"
            onLoad={handleSplineLoad}
          />
        </div>
      </div>

      {/* AAW LOGO — Top Left */}
      <div style={{
        position: 'absolute',
        top: '24px',
        left: '28px',
        zIndex: 100,
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
      }}>
        <img
          src="/aaw.png"
          alt="AAW Group Logo"
          style={{
            height: '52px',
            filter: 'brightness(0) invert(1) drop-shadow(0 0 12px rgba(34,211,238,0.35))',
          }}
        />
      </div>

      {/* HOLOGRAPHIC OVERLAY HUB */}
      <div className="upload-hub" style={{ zIndex: 10, position: 'absolute', bottom: '2vh', width: '100%', maxWidth: '440px', padding: '0 20px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        
        <div
          className={`premium-card ${isDragging ? 'dragging' : ''}`}
          style={{ width: '100%', border: '1px solid rgba(34, 211, 238, 0.15)' }}
          onDragEnter={onDragEnter}
          onDragLeave={onDragLeave}
          onDragOver={onDragOver}
          onDrop={onDrop}
          onMouseMove={handleMouseMove}
        >
          <div className="intake-ring" style={{ borderColor: 'rgba(34, 211, 238, 0.1)' }} />
          
          {fileQueue.length > 0 ? (
            <div className="queue-state fade-in text-center">
              <h2 className="card-title" style={{ fontFamily: '"Space Grotesk", sans-serif', marginBottom: '0.5rem', fontSize: '1.1rem', color: '#fff' }}>
                {fileQueue.length} VECTORS SYNCED
              </h2>
              
              <div className="holographic-tray-list" style={{ 
                maxHeight: '220px', overflowY: 'auto', marginBottom: '1.5rem', 
                padding: '10px', borderRadius: '12px', background: 'rgba(0,0,0,0.2)',
                border: '1px solid rgba(255,255,255,0.05)', display: 'flex', flexDirection: 'column', gap: '8px'
              }}>
                {fileQueue.map((f, i) => (
                  <div key={i} className="data-chip-full" style={{ 
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '8px 12px', background: 'rgba(34, 211, 238, 0.04)', 
                    border: '1px solid rgba(34, 211, 238, 0.15)', borderRadius: '10px',
                    animation: 'fade-in 0.3s ease'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', overflow: 'hidden' }}>
                      <div className="chip-status" style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent-cyan)', boxShadow: '0 0 10px var(--accent-cyan)' }} />
                      <span style={{ fontSize: '0.75rem', color: '#fff', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{f.name}</span>
                    </div>
                    <button 
                      onClick={(e) => { e.stopPropagation(); removeFile(i); }}
                      style={{ 
                        background: 'transparent', border: 'none', color: '#f87171', 
                        fontSize: '1rem', cursor: 'pointer', padding: '0 4px', 
                        display: 'flex', alignItems: 'center', transition: 'all 0.2s'
                      }}
                      onMouseEnter={(e) => e.target.style.transform = 'scale(1.2)'}
                      onMouseLeave={(e) => e.target.style.transform = 'scale(1)'}
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>

              <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
                <button className="btn-primary" style={{ 
                  background: 'rgba(255,255,255,0.02)', 
                  color: '#94a3b8', 
                  border: '1px solid rgba(255,255,255,0.05)', 
                  padding: '0.6rem 1.2rem', 
                  fontSize: '0.8rem',
                  borderRadius: '12px'
                }} onClick={() => setFileQueue([])}>
                  PURGE
                </button>
                <button className="btn-primary" onClick={submitBatch} style={{ 
                  background: 'linear-gradient(135deg, var(--accent-cyan) 0%, var(--accent-2) 100%)',
                  boxShadow: '0 0 25px var(--accent-cyan-glow)', 
                  border: 'none',
                  padding: '0.6rem 1.4rem',
                  fontSize: '0.85rem',
                  fontWeight: 700,
                  color: '#000',
                  borderRadius: '12px'
                }}>
                  INITIALIZE SYNTHESIS
                </button>
              </div>
            </div>
          ) : (
            <div className="idle-state fade-in">
              <div style={{ position: 'relative', width: 'fit-content', margin: '0 auto 0.8rem auto' }}>
                <span className="card-icon" style={{ fontSize: '2rem', margin: 0 }}>
                  {isDragging ? '⚡' : '💠'}
                </span>
                <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', width: '140%', height: '140%', border: '1px solid rgba(34, 211, 238, 0.2)', borderRadius: '50%', animation: 'ping 2s cubic-bezier(0, 0, 0.2, 1) infinite' }} />
              </div>

              <h2 className="card-title" style={{ fontFamily: '"Space Grotesk", sans-serif', fontSize: '1.2rem', marginBottom: '0.2rem', color: '#fff', letterSpacing: '-0.02em' }}>
                {isDragging ? 'RELEASE TO UPLOAD' : 'AWAITING VECTORS'}
              </h2>
              <p className="card-subtitle" style={{ marginBottom: '1.2rem', fontSize: '0.75rem', color: 'rgba(255,255,255,0.4)', letterSpacing: '0.05em' }}>
                SECURE TRIPLE-ENGINE EXTRACTION READY
              </p>
              
              <input
                ref={fileInputRef} type="file" hidden multiple
                accept=".pdf,.docx,.doc,.xlsx,.xls,.jpg,.jpeg,.png,.tiff,.tif"
                onChange={(e) => handleFiles(e.target.files)}
              />
              
              <button className="btn-primary" 
                style={{ 
                  background: 'rgba(34, 211, 238, 0.1)', 
                  border: '1px solid rgba(34, 211, 238, 0.3)', 
                  color: 'var(--accent-cyan)',
                  padding: '0.6rem 1.5rem', 
                  fontSize: '0.85rem',
                  borderRadius: '12px',
                  fontWeight: 600,
                  backdropFilter: 'blur(10px)'
                }} 
                onClick={() => fileInputRef.current?.click()}
              >
                SELECT BATCH
              </button>
            </div>
          )}
        </div>

        <div className="signature-section" style={{ marginTop: '1.2rem' }}>
          <div className="signature-tagline" style={{ fontFamily: '"Space Grotesk", sans-serif', fontSize: '0.55rem', letterSpacing: '0.4em', color: 'rgba(255,255,255,0.3)', marginTop: '0.4rem' }}>POWERED BY AAW-AI</div>
        </div>
      </div>
    </div>
  )
}
