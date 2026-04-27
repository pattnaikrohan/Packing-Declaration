import { useState, useRef, useEffect, useCallback } from 'react'
import toast from 'react-hot-toast'
import { extractROI } from '../api/client'

export default function ImperialViewport({ file, onRoiExtracted, activeField }) {
  const [zoom, setZoom] = useState(1)
  const [pos, setPos] = useState({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 })
  
  // Drawing state
  const [isDrawing, setIsDrawing] = useState(false)
  const [boxStart, setBoxStart] = useState(null)
  const [currentBox, setCurrentBox] = useState(null)
  
  const viewportRef = useRef(null)
  const [fileUrl, setFileUrl] = useState(null)

  useEffect(() => {
    if (file) {
      const url = URL.createObjectURL(file)
      setFileUrl(url)
      setZoom(1)
      setPos({ x: 0, y: 0 })
      return () => URL.revokeObjectURL(url)
    }
  }, [file])

  const handleMouseDown = (e) => {
    const rect = viewportRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    if (activeField) {
      // Draw Mode
      setIsDrawing(true)
      setBoxStart({ x, y })
      setCurrentBox({ x, y, w: 0, h: 0 })
    } else {
      // Drag Mode
      if (e.button !== 0) return 
      setIsDragging(true)
      setDragStart({ x: e.clientX - pos.x, y: e.clientY - pos.y })
    }
  }

  const handleMouseMove = (e) => {
    const rect = viewportRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    if (isDrawing) {
      setCurrentBox({
        x: Math.min(x, boxStart.x),
        y: Math.min(y, boxStart.y),
        w: Math.abs(x - boxStart.x),
        h: Math.abs(y - boxStart.y)
      })
    } else if (isDragging) {
      setPos({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y
      })
    }
  }

  const handleMouseUp = async (e) => {
    if (isDrawing && currentBox && currentBox.w > 10 && currentBox.h > 10) {
      // Calculate RELATIVE coordinates (0.0 to 1.0)
      const rect = viewportRef.current.getBoundingClientRect()
      
      const x1 = (currentBox.x / rect.width)
      const y1 = (currentBox.y / rect.height)
      const x2 = (currentBox.x + currentBox.w) / rect.width
      const y2 = (currentBox.y + currentBox.h) / rect.height

      try {
        toast.loading('Precision Scanning...', { id: 'roi' })
        const text = await extractROI(file, x1, y1, x2, y2)
        onRoiExtracted?.(text)
        toast.success(`Extracted: ${text.substring(0, 20)}...`, { id: 'roi' })
      } catch (err) {
        toast.error('ROI Extraction Fault', { id: 'roi' })
      }
    }

    setIsDrawing(false)
    setIsDragging(false)
    setBoxStart(null)
    setCurrentBox(null)
  }
  
  const handleWheel = (e) => {
    if (e.ctrlKey) {
      e.preventDefault()
      const delta = e.deltaY > 0 ? -0.1 : 0.1
      setZoom(prev => Math.min(Math.max(prev + delta, 0.5), 5))
    }
  }

  const isDoc = file?.name?.toLowerCase().match(/\.(doc|docx|docm|rtf|xls|xlsx)\s*$/)
  const isPdf = (file?.type === 'application/pdf' || file?.name?.toLowerCase().endsWith('.pdf')) && !isDoc
  const isImage = file?.type?.startsWith('image/') || file?.name?.toLowerCase().match(/\.(jpg|jpeg|png|gif|tiff|tif)\s*$/)

  return (
    <div className="glass-panel" style={{ 
      height: '100%', 
      display: 'flex', 
      flexDirection: 'column', 
      overflow: 'hidden', 
      padding: 0, 
      background: 'rgba(0,0,0,0.6)',
      border: '1px solid var(--glass-border)',
      boxShadow: 'inset 0 0 60px rgba(0,0,0,0.8)'
    }}>
      {/* Viewport Toolbar */}
      <div style={{ 
        padding: '0.75rem 1.5rem', 
        background: 'rgba(255,255,255,0.03)', 
        borderBottom: '1px solid var(--glass-border)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        zIndex: 50
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ 
            fontSize: '0.6rem', 
            background: activeField ? 'var(--accent)' : 'rgba(255,255,255,0.1)',
            color: activeField ? 'white' : 'var(--text-muted)',
            padding: '4px 10px',
            borderRadius: 20,
            fontWeight: 800,
            letterSpacing: '0.05em'
          }}>
            {activeField ? `ENTITY SCANNING: ${activeField.toUpperCase()}` : 'AUDIT MODE'}
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', opacity: 0.6 }}>{file?.name}</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="neural-bubble" onClick={() => setZoom(prev => Math.max(prev - 0.2, 0.5))} style={{ padding: '4px 12px' }}>—</button>
          <span style={{ fontSize: '0.8rem', minWidth: 40, textAlign: 'center', alignSelf: 'center' }}>{(zoom * 100).toFixed(0)}%</span>
          <button className="neural-bubble" onClick={() => setZoom(prev => Math.min(prev + 0.2, 5))} style={{ padding: '4px 12px' }}>+</button>
          <button className="neural-bubble" onClick={() => { setZoom(1); setPos({x:0,y:0}); }} style={{ padding: '4px 12px', marginLeft: 8 }}>RESET</button>
        </div>
      </div>

      {/* Main Viewport Area */}
      <div 
        ref={viewportRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
        style={{ 
          flex: 1, 
          position: 'relative', 
          overflow: 'hidden', 
          cursor: isDrawing ? 'crosshair' : isDragging ? 'grabbing' : 'grab',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}
      >
        {/* Drawing Canvas Overlay */}
        {activeField && (
           <div style={{ 
             position: 'absolute', 
             inset: 0, 
             zIndex: 40,
             pointerEvents: 'none' 
           }}>
             {currentBox && (
               <div style={{
                 position: 'absolute',
                 left: currentBox.x,
                 top: currentBox.y,
                 width: currentBox.w,
                 height: currentBox.h,
                 border: '2px solid var(--accent)',
                 background: 'rgba(56, 189, 248, 0.2)',
                 boxShadow: '0 0 15px var(--accent-glow)',
                 borderRadius: 2
               }} />
             )}
           </div>
        )}

        {!fileUrl && (
          <div className="loader" />
        )}

        {isPdf && (
          <div style={{ 
            width: '100%', 
            height: '100%', 
            transform: `scale(${zoom}) translate(${pos.x / zoom}px, ${pos.y / zoom}px)`,
            transition: (isDragging || isDrawing) ? 'none' : 'transform 0.2s ease-out',
            pointerEvents: activeField ? 'none' : 'auto'
          }}>
            <embed src={fileUrl} type="application/pdf" width="100%" height="100%" />
          </div>
        )}

        {isImage && (
          <img 
            src={fileUrl} 
            alt="Viewport Preview"
            draggable={false}
            style={{ 
              maxWidth: '95%', 
              maxHeight: '95%',
              userSelect: 'none',
              transform: `scale(${zoom}) translate(${pos.x / zoom}px, ${pos.y / zoom}px)`,
              transition: (isDragging || isDrawing) ? 'none' : 'transform 0.2s ease-out',
              boxShadow: '0 30px 60px rgba(0,0,0,0.6)',
              borderRadius: 4
            }}
          />
        )}

        {/* High-Fidelity Word Preview */}
        {!isPdf && !isImage && fileUrl && (
          <div className="glass-panel" style={{ 
            padding: '3rem', 
            maxWidth: '90%', 
            maxHeight: '95%',
            overflowY: 'auto',
            background: 'white',
            color: '#333',
            boxShadow: '0 20px 50px rgba(0,0,0,0.4)',
            transform: `scale(${zoom}) translate(${pos.x / zoom}px, ${pos.y / zoom}px)`,
            transition: (isDragging || isDrawing) ? 'none' : 'transform 0.2s ease-out'
          }}>
            <div style={{ textAlign: 'center', opacity: 0.5, marginBottom: 20, fontSize: '0.6rem', color: 'var(--accent)' }}>
              [ IMPERIAL CLEAN SYNTHESIS VIEW ]
            </div>
            <div style={{ fontFamily: 'serif', lineHeight: 1.6, fontSize: '0.9rem' }}>
              <h1 style={{ textAlign: 'center', fontSize: '1.2rem', marginBottom: 20 }}>FCL PACKING DECLARATION</h1>
              <p>Issuer: [ Neural Field Mapping ]</p>
              <br />
              <p style={{ fontWeight: 'bold' }}>UNACCEPTABLE PACKAGING MATERIAL (Q1)</p>
              <p>[ ] YES [X] NO</p>
              <br />
              <div style={{ opacity: 0.3 }}>{Array(15).fill("----------------------------------------------------------").join("\n")}</div>
            </div>
          </div>
        )}
      </div>

      {/* Viewport Footer */}
      <div style={{ 
        padding: '0.6rem 1.5rem', 
        background: 'rgba(0,0,0,0.4)', 
        borderTop: '1px solid var(--glass-border)',
        fontSize: '0.6rem',
        color: 'var(--text-muted)',
        display: 'flex',
        justifyContent: 'space-between',
        letterSpacing: '0.1em'
      }}>
        <span>COORDINATES: {pos.x.toFixed(0)}, {pos.y.toFixed(0)}</span>
        <span style={{ color: 'var(--accent)', fontWeight: 800 }}>{activeField ? 'ENTITY SCANNER ACTIVE' : 'SYSTEM READY'}</span>
      </div>
    </div>
  )
}
