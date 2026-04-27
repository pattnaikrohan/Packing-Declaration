import { useEffect, useRef } from 'react'

/**
 * EyeSpotlight — soft volumetric light rays from the robot's eyes toward 
 * wherever the user's mouse hovers. Looks like two flashlight/spotlight beams,
 * NOT laser lines. Uses layered radial + conic gradients for a natural falloff.
 */
export default function EyeSpotlight() {
  const canvasRef = useRef(null)
  const mouseRef  = useRef({ x: -999, y: -999 })
  const animRef   = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')

    // Resize canvas to match window
    const resize = () => {
      canvas.width  = canvas.parentElement?.offsetWidth  || window.innerWidth
      canvas.height = canvas.parentElement?.offsetHeight || window.innerHeight
    }
    resize()
    const ro = new ResizeObserver(resize)
    if (canvas.parentElement) ro.observe(canvas.parentElement)

    // Track mouse anywhere on the page
    const onMove = (e) => {
      const rect = canvas.getBoundingClientRect()
      mouseRef.current = {
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      }
    }
    window.addEventListener('mousemove', onMove)

    // ── Eye positions as fraction of canvas ──────────────────────
    // These match the white eyes on the robot in the screenshot
    // (roughly center-top of the hero area)
    const EYES = [
      { fx: 0.435, fy: 0.24 },  // left eye
      { fx: 0.515, fy: 0.24 },  // right eye
    ]

    // ── Draw one soft spotlight cone ─────────────────────────────
    function drawSpotlight(ex, ey, mx, my) {
      const dx   = mx - ex
      const dy   = my - ey
      const dist = Math.sqrt(dx * dx + dy * dy) || 1
      const nx   = dx / dist
      const ny   = dy / dist

      // How far the beam extends (to cursor + a bit beyond)
      const beamLen = Math.min(dist + 120, 600)

      // Tip of the beam
      const tx = ex + nx * beamLen
      const ty = ey + ny * beamLen

      // Perpendicular axis for the cone spread
      const px = -ny
      const py =  nx

      // ── LAYER 1: Wide, very soft outer glow cone ─────────────
      const wideSpread = beamLen * 0.55   // wide fan — like a real flashlight
      ctx.save()
      ctx.globalAlpha = 0.10

      const outerGrad = ctx.createRadialGradient(ex, ey, 0, ex, ey, beamLen)
      outerGrad.addColorStop(0,   'rgba(180, 215, 255, 1)')
      outerGrad.addColorStop(0.4, 'rgba(140, 190, 255, 0.4)')
      outerGrad.addColorStop(1,   'rgba(100, 160, 255, 0)')

      ctx.beginPath()
      ctx.moveTo(ex, ey)
      ctx.lineTo(tx + px * wideSpread, ty + py * wideSpread)
      // Arc across the tip for a rounded spotlight edge
      ctx.arc(tx, ty, wideSpread, Math.atan2(py, px), Math.atan2(py, px) + Math.PI, true)
      ctx.lineTo(tx - px * wideSpread, ty - py * wideSpread)
      ctx.closePath()
      ctx.fillStyle = outerGrad
      ctx.fill()
      ctx.restore()

      // ── LAYER 2: Medium cone ─────────────────────────────────
      const midSpread = beamLen * 0.30
      ctx.save()
      ctx.globalAlpha = 0.18

      const midGrad = ctx.createRadialGradient(ex, ey, 0, ex, ey, beamLen)
      midGrad.addColorStop(0,   'rgba(210, 230, 255, 1)')
      midGrad.addColorStop(0.5, 'rgba(160, 200, 255, 0.5)')
      midGrad.addColorStop(1,   'rgba(120, 170, 255, 0)')

      ctx.beginPath()
      ctx.moveTo(ex, ey)
      ctx.lineTo(tx + px * midSpread, ty + py * midSpread)
      ctx.arc(tx, ty, midSpread, Math.atan2(py, px), Math.atan2(py, px) + Math.PI, true)
      ctx.lineTo(tx - px * midSpread, ty - py * midSpread)
      ctx.closePath()
      ctx.fillStyle = midGrad
      ctx.fill()
      ctx.restore()

      // ── LAYER 3: Bright inner core ───────────────────────────
      const coreSpread = beamLen * 0.08
      ctx.save()
      ctx.globalAlpha = 0.40

      const coreGrad = ctx.createLinearGradient(ex, ey, tx, ty)
      coreGrad.addColorStop(0,   'rgba(240, 248, 255, 0.9)')
      coreGrad.addColorStop(0.3, 'rgba(200, 225, 255, 0.6)')
      coreGrad.addColorStop(1,   'rgba(150, 200, 255, 0)')

      ctx.beginPath()
      ctx.moveTo(ex, ey)
      ctx.lineTo(tx + px * coreSpread, ty + py * coreSpread)
      ctx.lineTo(tx - px * coreSpread, ty - py * coreSpread)
      ctx.closePath()
      ctx.fillStyle = coreGrad
      ctx.fill()
      ctx.restore()

      // ── LAYER 4: Eye socket glow ─────────────────────────────
      ctx.save()
      const eyeGlow = ctx.createRadialGradient(ex, ey, 0, ex, ey, 18)
      eyeGlow.addColorStop(0,   'rgba(255, 255, 255, 0.95)')
      eyeGlow.addColorStop(0.3, 'rgba(200, 225, 255, 0.7)')
      eyeGlow.addColorStop(0.7, 'rgba(150, 190, 255, 0.3)')
      eyeGlow.addColorStop(1,   'rgba(100, 160, 255, 0)')

      ctx.beginPath()
      ctx.arc(ex, ey, 18, 0, Math.PI * 2)
      ctx.fillStyle = eyeGlow
      ctx.fill()
      ctx.restore()
    }

    // ── Animation loop ───────────────────────────────────────────
    const draw = () => {
      const { width, height } = canvas
      ctx.clearRect(0, 0, width, height)

      const { x: mx, y: my } = mouseRef.current
      if (mx === -999) {
        animRef.current = requestAnimationFrame(draw)
        return
      }

      // Draw both eye spotlights
      EYES.forEach(({ fx, fy }) => {
        drawSpotlight(fx * width, fy * height, mx, my)
      })

      animRef.current = requestAnimationFrame(draw)
    }

    animRef.current = requestAnimationFrame(draw)

    return () => {
      cancelAnimationFrame(animRef.current)
      window.removeEventListener('mousemove', onMove)
      ro.disconnect()
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      style={{
        position:      'absolute',
        top:           0,
        left:          0,
        width:         '100%',
        height:        '100%',
        pointerEvents: 'none',
        zIndex:        6,
        // 'screen' makes the light ADD to what's beneath, like real light
        mixBlendMode:  'screen',
      }}
    />
  )
}
