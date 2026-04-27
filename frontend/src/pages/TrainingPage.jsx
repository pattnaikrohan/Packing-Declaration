import { useRef } from 'react'
import { Link } from 'react-router-dom'
import TrainingUploadQueue from '../components/TrainingUploadQueue'
import TrainingJobStatus from '../components/TrainingJobStatus'
import ModelStatsCard from '../components/ModelStatsCard'

export default function TrainingPage() {
  const jobSectionRef = useRef(null)

  function handleJobQueued() {
    // Auto-scroll to job status section
    setTimeout(() => {
      jobSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 300)
  }

  return (
    <div className="fade-in" style={{ height: '100vh', padding: '2rem', overflowY: 'auto' }}>
      <header style={{ marginBottom: 48, display: 'flex', alignItems: 'center', gap: '2rem' }}>
        <Link to="/" className="back-btn-neural" style={{ textDecoration: 'none' }}>
           <span style={{ fontSize: '1.2rem' }}>←</span>
        </Link>
        <div>
          <h1 className="glow-text" style={{ fontSize: '2.5rem', fontWeight: 800, marginBottom: 8, margin: 0 }}>
            Neural Training Studio
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '1rem', fontWeight: 300, margin: 0 }}>
            Manage your machine learning corpus and optimize extraction matrices in real-time.
          </p>
        </div>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '2.5rem' }}>
        {/* Section 1 — Corpus & Model */}
        <div className="fade-in" style={{ animationDelay: '0.1s' }}>
          <ModelStatsCard />
        </div>

        {/* Section 2 — Bulk Upload */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
           <div className="fade-in" style={{ animationDelay: '0.2s' }}>
             <TrainingUploadQueue onJobQueued={handleJobQueued} />
           </div>
           <div ref={jobSectionRef} className="fade-in" style={{ animationDelay: '0.3s' }}>
             <TrainingJobStatus />
           </div>
        </div>
      </div>
    </div>
  )
}
