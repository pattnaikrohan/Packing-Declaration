import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import ScoreGauge from '../components/ScoreGauge'
import ResultPanel from '../components/ResultPanel'
import { submitToDAFF, setOutcome } from '../api/client'

export default function ResultPage() {
  const { state } = useLocation()
  const navigate = useNavigate()
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [submitResult, setSubmitResult] = useState(null)

  const { canonical, result } = state || {}
  if (!result) { navigate('/'); return null }

  const passed = result.passed
  const score = result.final_score

  async function handleSubmit() {
    setSubmitting(true)
    try {
      const res = await submitToDAFF(result.record_id, canonical, result)
      setSubmitResult(res)
      setSubmitted(true)

      // Also label the record
      await setOutcome(result.record_id, passed ? 'accepted' : 'rejected').catch(() => {})

      toast.success(res.mock
        ? `Mock mode — would send to DAFF ${passed ? 'PROCEED' : 'REJECT'} flow`
        : `Submitted to DAFF (HTTP ${res.response_code})`
      )
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Submission failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      {/* Pass/Fail banner */}
      <div className={`result-banner ${passed ? 'pass' : 'fail'}`}>
        <span className="result-banner-icon">{passed ? '✅' : '❌'}</span>
        <div>
          <div className="result-banner-title" style={{ color: passed ? 'var(--color-success)' : 'var(--color-danger)' }}>
            {passed ? 'Declaration Accepted' : 'Declaration Rejected'}
          </div>
          <div className="result-banner-sub">
            {result.error_count} error{result.error_count !== 1 ? 's' : ''} · {result.warning_count} warning{result.warning_count !== 1 ? 's' : ''} · Score {score}/100
          </div>
        </div>
      </div>

      {/* Two-column: gauge + rules */}
      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 20, alignItems: 'start' }}>
        {/* Left: gauge */}
        <div className="card" style={{ textAlign: 'center' }}>
          <ScoreGauge score={score} size={240} />
          <div className="divider" />
          <div style={{ fontSize: 12, color: 'var(--color-text-muted)', lineHeight: 1.8 }}>
            <div>Rule Score: <strong>{result.rule_score}</strong> / 90</div>
            <div>ML Adjustment: <strong>{result.ml_active ? (result.ml_bonus >= 0 ? '+' : '') + result.ml_bonus.toFixed(1) : 'inactive'}</strong></div>
            <div>Declaration: <strong>{result.declaration_type || '—'}</strong></div>
          </div>
        </div>

        {/* Right: rules */}
        <div className="card">
          <h2 className="section-title" style={{ marginBottom: 16 }}>Validation Results</h2>
          <ResultPanel
            ruleOutcomes={result.rule_outcomes}
            mlBonus={result.ml_bonus}
            mlActive={result.ml_active}
          />
        </div>
      </div>

      {/* Submit */}
      <div style={{ display: 'none' }}>
        {!submitted ? (
          <div className="card" style={{ marginTop: 20, display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 700, marginBottom: 2 }}>Submit to DAFF</div>
              <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
                Sends a signed webhook to the Power Automate {passed ? 'proceed' : 'rejection'} flow.
              </div>
            </div>
            <button id="btn-submit" className={`btn btn-lg ${passed ? 'btn-success' : 'btn-danger'}`}
              onClick={handleSubmit} disabled={submitting}>
              {submitting ? <><span className="spinner" /> Submitting…</> : `→ Submit to DAFF`}
            </button>
            <button className="btn btn-secondary" onClick={() => navigate('/')}>New Declaration</button>
          </div>
        ) : (
          <div className="card" style={{ marginTop: 20, background: 'var(--color-success-dim)', border: '1px solid rgba(16,185,129,0.3)' }}>
            <div style={{ fontWeight: 700, color: 'var(--color-success)', marginBottom: 4 }}>
              ✓ Submitted {submitResult?.mock ? '(mock mode)' : `— HTTP ${submitResult?.response_code}`}
            </div>
            <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 12 }}>
              Record ID: <code>{result.record_id}</code>
            </div>
            <button className="btn btn-secondary" onClick={() => navigate('/')}>→ New Declaration</button>
          </div>
        )}
      </div>
    </div>
  )
}
