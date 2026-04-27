import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { getMLStats, trainModel } from '../api/client'

function MetricCard({ value, label, color }) {
  return (
    <div className="insight-card" style={{ padding: '1.25rem', border: '1px solid var(--border-color)', borderRadius: 12 }}>
      <div style={{ fontSize: '1.75rem', fontWeight: 800, color: color || 'var(--accent)', marginBottom: 4 }}>{value}</div>
      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
    </div>
  )
}

export default function ModelStatsCard() {
  const [stats, setStats] = useState(null)
  const [optimizing, setOptimizing] = useState(false)

  async function fetchStats() {
    try {
      const data = await getMLStats()
      setStats(data)
    } catch (_) {}
  }

  useEffect(() => {
    fetchStats()
    const interval = setInterval(fetchStats, 15000)
    return () => clearInterval(interval)
  }, [])

  async function handleOptimize() {
    setOptimizing(true)
    try {
      const res = await trainModel()
      if (res.status === 'success') {
        toast.success(`Matrix Optimized! Accuracy: ${(res.accuracy_estimate * 100).toFixed(1)}%`)
        fetchStats()
      } else {
        toast.error(res.message || 'Optimization failed')
      }
    } catch (err) {
      toast.error('Neural engine failure')
    } finally {
      setOptimizing(false)
    }
  }

  if (!stats) {
    return <div className="loader" style={{ margin: '40px auto' }} />
  }

  return (
    <div className="glass-panel" style={{ padding: '2rem', display: 'none' }}>
    </div>
  )
}
