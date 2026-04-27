import { useEffect, useRef, useState } from 'react'
import { listTrainingJobs } from '../api/client'

function formatTime(iso) {
  if (!iso) return '--'
  return new Date(iso).toLocaleTimeString()
}

function StatusBadge({ status }) {
  const label = status.charAt(0).toUpperCase() + status.slice(1)
  return (
    <span className={`badge ${status}`}>
      <span className="badge-dot" />
      {label}
    </span>
  )
}

function ProgressBar({ done, total }) {
  const pct = total > 0 ? (done / total) * 100 : 0
  return (
    <div className="progress-bar-wrap">
      <div className="progress-bar-fill" style={{ width: `${pct}%` }} />
    </div>
  )
}

const TERMINAL = ['done', 'failed']

export default function TrainingJobStatus() {
  const [jobs, setJobs] = useState([])
  const intervalRef = useRef(null)

  async function fetchJobs() {
    try {
      const data = await listTrainingJobs()
      setJobs(data)
    } catch (_) {}
  }

  useEffect(() => {
    fetchJobs()
    intervalRef.current = setInterval(() => {
      fetchJobs().then(() => {
        // Stop polling when all jobs are terminal
        setJobs((prev) => {
          const allDone = prev.every((j) => TERMINAL.includes(j.status))
          if (allDone && intervalRef.current) {
            clearInterval(intervalRef.current)
            intervalRef.current = null
          }
          return prev
        })
      })
    }, 2000)
    return () => clearInterval(intervalRef.current)
  }, [])

  // Restart polling when new job appears
  useEffect(() => {
    const hasActive = jobs.some((j) => !TERMINAL.includes(j.status))
    if (hasActive && !intervalRef.current) {
      intervalRef.current = setInterval(fetchJobs, 2000)
    }
  }, [jobs])

  if (jobs.length === 0) {
    return (
      <div className="card">
        <h2 className="section-title">Training Jobs</h2>
        <p style={{ color: 'var(--color-text-faint)', fontSize: 13, paddingTop: 12 }}>
          No training jobs yet. Upload some declarations above to get started.
        </p>
      </div>
    )
  }

  return (
    <div className="card">
      <h2 className="section-title" style={{ marginBottom: 16 }}>Training Jobs</h2>

      {jobs.map((job) => {
        const totalRecords = job.total_files
        const labelText = job.label === 'force_retrain'
          ? 'Force Retrain'
          : job.label === 'accepted' ? 'Accepted batch' : 'Rejected batch'

        return (
          <div key={job.job_id} className="job-card">
            <div className="job-card-header">
              <StatusBadge status={job.status} />
              <span className="job-card-title">{labelText}</span>
              <span className="job-card-time">
                Started {formatTime(job.started_at)}
                {job.finished_at ? ` · Finished ${formatTime(job.finished_at)}` : ''}
              </span>
            </div>

            {totalRecords > 0 && (
              <>
                <ProgressBar done={job.processed_files} total={totalRecords} />
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--color-text-muted)' }}>
                  <span>{job.processed_files} of {totalRecords} files processed</span>
                  <span>{job.records_added} record{job.records_added !== 1 ? 's' : ''} added</span>
                </div>
              </>
            )}

            {/* Failed files */}
            {job.failed_files?.length > 0 && (
              <details style={{ marginTop: 8 }}>
                <summary style={{ fontSize: 12, color: 'var(--color-danger)', cursor: 'pointer' }}>
                  {job.failed_files.length} file{job.failed_files.length > 1 ? 's' : ''} failed
                </summary>
                <ul style={{ paddingLeft: 20, fontSize: 11, color: 'var(--color-text-muted)', marginTop: 4 }}>
                  {job.failed_files.map((f) => <li key={f}>{f}</li>)}
                </ul>
              </details>
            )}

            {/* Result banners */}
            {job.status === 'done' && job.model_swapped && (
              <div className="job-banner swapped">
                🚀 Model updated — F1 improved from {job.old_f1?.toFixed(3) ?? '—'} to {job.new_f1?.toFixed(3)}
              </div>
            )}
            {job.status === 'done' && !job.model_swapped && job.new_f1 !== null && job.new_f1 !== undefined && (
              <div className="job-banner unchanged">
                Model unchanged — existing model performs better (F1: {job.old_f1?.toFixed(3) ?? '—'})
              </div>
            )}
            {job.status === 'done' && job.new_f1 === null && (
              <div className="job-banner needs-more">
                ℹ️ Model training needs at least 20 records. Upload more to activate ML scoring.
              </div>
            )}

            {job.status === 'failed' && (
              <div className="job-banner" style={{ background: 'var(--color-danger-dim)', color: 'var(--color-danger)', border: '1px solid rgba(239,68,68,0.3)' }}>
                ❌ {job.error || 'Unknown error'}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
