import { useEffect, useRef } from 'react'

const SCORE_COLORS = {
  red: '#ef4444',
  amber: '#f59e0b',
  sky: '#38bdf8',
}

function getColor(score) {
  if (score >= 85) return SCORE_COLORS.sky
  if (score >= 60) return SCORE_COLORS.amber
  return SCORE_COLORS.red
}

export default function ScoreGauge({ score, size = 260 }) {
  const canvasRef = useRef(null)
  const animRef = useRef(null)
  const currentRef = useRef(0)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const dpr = window.devicePixelRatio || 1
    canvas.width = size * dpr
    canvas.height = (size * 0.7) * dpr
    ctx.scale(dpr, dpr)

    const cx = size / 2
    const cy = size * 0.55
    const r = size * 0.38
    const startAngle = Math.PI
    const endAngle = 2 * Math.PI
    const color = getColor(score)

    cancelAnimationFrame(animRef.current)

    function draw(current) {
      ctx.clearRect(0, 0, size, size)

      // Background track
      ctx.beginPath()
      ctx.arc(cx, cy, r, startAngle, endAngle)
      ctx.strokeStyle = 'rgba(255,255,255,0.04)'
      ctx.lineWidth = 14
      ctx.lineCap = 'round'
      ctx.stroke()

      // Zones
      const drawZone = (start, end, zoneColor) => {
        ctx.beginPath()
        ctx.arc(cx, cy, r, startAngle + (start/100)*Math.PI, startAngle + (end/100)*Math.PI)
        ctx.strokeStyle = zoneColor
        ctx.lineWidth = 4
        ctx.stroke()
      }
      
      drawZone(0, 60, 'rgba(239, 68, 68, 0.2)')
      drawZone(60, 85, 'rgba(245, 158, 11, 0.2)')
      drawZone(85, 100, 'rgba(56, 189, 248, 0.2)')

      // Score arc
      const arcEnd = startAngle + (current / 100) * Math.PI
      ctx.beginPath()
      ctx.arc(cx, cy, r, startAngle, Math.max(startAngle, arcEnd))
      ctx.strokeStyle = color
      ctx.lineWidth = 14
      ctx.lineCap = 'round'
      
      // Outer glow
      ctx.shadowColor = color
      ctx.shadowBlur = 15
      ctx.stroke()
      ctx.shadowBlur = 0

      // Pass threshold marker at 85
      const markerAngle = startAngle + (85 / 100) * Math.PI
      const mx = cx + r * Math.cos(markerAngle)
      const my = cy + r * Math.sin(markerAngle)
      ctx.beginPath()
      ctx.arc(mx, my, 4, 0, Math.PI * 2)
      ctx.fillStyle = '#fff'
      ctx.fill()
      ctx.lineWidth = 2
      ctx.strokeStyle = SCORE_COLORS.sky
      ctx.stroke()

      // Score number
      ctx.textAlign = 'center'
      ctx.textBaseline = 'bottom'
      ctx.font = `700 ${size * 0.25}px Outfit, sans-serif`
      ctx.fillStyle = '#fff'
      
      // Subtle number glow
      ctx.shadowColor = 'rgba(255,255,255,0.3)'
      ctx.shadowBlur = 10
      ctx.fillText(Math.round(current), cx, cy + 8)
      ctx.shadowBlur = 0

      // Label
      ctx.font = `600 ${size * 0.05}px Outfit, sans-serif`
      ctx.fillStyle = 'var(--text-muted)'
      ctx.letterSpacing = '2px'
      ctx.fillText('COMPLIANCE VECTOR', cx, cy + size * 0.14)
    }

    function animate() {
      if (currentRef.current < score) {
        currentRef.current = Math.min(currentRef.current + 1.2, score)
        draw(currentRef.current)
        animRef.current = requestAnimationFrame(animate)
      } else {
        draw(score)
      }
    }

    animate()
    return () => cancelAnimationFrame(animRef.current)
  }, [score, size])

  return (
    <div className="fade-in">
        <canvas
        ref={canvasRef}
        style={{ width: size, height: size * 0.7, display: 'block', margin: '0 auto' }}
        />
    </div>
  )
}
