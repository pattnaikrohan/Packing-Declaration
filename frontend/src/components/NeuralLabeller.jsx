import { useState, useEffect } from 'react'
import toast from 'react-hot-toast'
import { submitLabelledFile, trainModel, getMLStats } from '../api/client'
import ImperialViewport from './ImperialViewport'

const ENTITY_FIELDS = [
  { id: 'issuer_company', label: 'Issuer Company' },
  { id: 'issuer_address', label: 'Issuer Address' },
  { id: 'vessel_name', label: 'Vessel Name' },
  { id: 'voyage_number', label: 'Voyage Number' },
  { id: 'consignment_ref', label: 'Consignment Ref' }
]

const OPTIONS = {
  declaration_type: ['FCL_ANNUAL', 'LCL_ANNUAL', 'FCL_SINGLE', 'LCL_SINGLE'],
  q1_unacceptable_material: ['YES', 'NO'],
  q2_timber_bamboo: ['YES_TIMBER', 'YES_BAMBOO', 'NO'],
  q3_treatment: ['ISPM15', 'DAFF_CERTIFIED', 'NOT_TREATED', 'NOT_APPLICABLE'],
  q4_cleanliness: ['PRESENT', 'ABSENT'],
  signed: ['SIGNED', 'UNSIGNED']
}

const LABELS = {
  declaration_type: 'Declaration Type',
  q1_unacceptable_material: 'Q1: Unacceptable Material',
  q2_timber_bamboo: 'Q2: Timber/Bamboo',
  q3_treatment: 'Q3: Treatment / ISPM15',
  q4_cleanliness: 'Q4: Container Cleanliness',
  signed: 'Signature Status'
}

export default function NeuralLabeller({ file, onComplete, queueInfo }) {
  const [selections, setSelections] = useState({
    issuer_company: '',
    issuer_address: '',
    vessel_name: '',
    voyage_number: '',
    consignment_ref: '',
    declaration_type: 'FCL_ANNUAL',
    q1_unacceptable_material: 'NO',
    q2_timber_bamboo: 'NO',
    q3_treatment: 'NOT_APPLICABLE',
    q4_cleanliness: 'PRESENT',
    signed: 'SIGNED'
  })

  const [activeField, setActiveField] = useState(null)
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(false)

  const fetchStats = async () => {
    try {
      const s = await getMLStats()
      setStats(s)
    } catch (e) {}
  }

  useEffect(() => {
    fetchStats()
  }, [])

  const handleSelect = (field, val) => {
    setSelections(prev => ({ ...prev, [field]: val }))
  }

  const handleSubmit = async () => {
    setLoading(true)
    try {
      await submitLabelledFile(file, selections)
      toast.success('Neural Matrix Updated!')
      onComplete?.()
    } catch (err) {
      toast.error('Labelling synchronization failed.')
    } finally {
      setLoading(false)
    }
  }

  const handleRetrain = async () => {
    toast.loading("Optimizing Neural Matrix...", { id: 'train' })
    try {
      const res = await trainModel()
      fetchStats()
      toast.success(`Matrix Synced: ${(res.accuracy_estimate * 100).toFixed(1)}% Accuracy`, { id: 'train' })
    } catch (e) {
      toast.error('Retraining failed.')
    }
  }

  const handleRoiExtracted = (text) => {
    if (activeField) {
      setSelections(prev => ({ ...prev, [activeField]: text }))
      setActiveField(null)
      toast.success(`Field mapped: ${text.substring(0, 15)}...`)
    }
  }

  return (
    <div className="fade-in" style={{ 
      display: 'grid', 
      gridTemplateColumns: '500px 1fr', 
      gap: '2.5rem', 
      height: '100vh',
      padding: '2rem'
    }}>
      
      {/* Selection Column (Architect Command) */}
      <div className="glass-panel" style={{ 
        display: 'flex', 
        flexDirection: 'column', 
        padding: '2.5rem',
        overflowY: 'auto',
        borderRadius: 0,
        border: 'none',
        background: 'rgba(255,255,255,0.01)',
        borderRight: '1px solid var(--glass-border)'
      }}>
        <div style={{ marginBottom: 32, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
            <button 
              onClick={() => onComplete?.(true)} // Pass true to signal explicit cancel/back
              className="back-btn-neural"
              style={{ padding: '8px 12px' }}
            >
              ←
            </button>
            <div>
              <h2 className="panel-title" style={{ fontSize: '1.4rem', marginBottom: 4 }}>
                <span className="glow-text">Neural Architect</span>
              </h2>
              <div style={{ fontSize: '0.6rem', color: 'var(--accent)', fontWeight: 800 }}>
                {queueInfo ? `BATCH QUEUE: ${queueInfo.current} / ${queueInfo.total}` : 'SINGLE SCAN'}
              </div>
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '0.6rem', opacity: 0.5 }}>ACCURACY</div>
            <div style={{ fontSize: '1.1rem', fontWeight: 900, color: 'var(--accent)' }}>
              {stats ? (stats.accuracy_estimate * 100).toFixed(1) : '--'}%
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          {/* Entity Drawing Fields */}
          <section>
             <h4 style={{ fontSize: '0.65rem', opacity: 0.5, letterSpacing: '0.1em', marginBottom: 12 }}>ENTITY MAPPING (DRAW BOX)</h4>
             <div style={{ display: 'grid', gap: 12 }}>
                {ENTITY_FIELDS.map(f => (
                  <div key={f.id} style={{ position: 'relative' }}>
                    <label style={{ fontSize: '0.6rem', opacity: 0.4, marginBottom: 2, display: 'block' }}>{f.label}</label>
                    <input 
                      type="text" 
                      value={selections[f.id]}
                      onChange={(e) => setSelections({...selections, [f.id]: e.target.value})}
                      placeholder="Click to start scan..."
                      onFocus={() => setActiveField(f.id)}
                      className="audit-input"
                      style={{ 
                        width: '100%', 
                        fontSize: '0.8rem',
                        paddingRight: 40,
                        borderColor: activeField === f.id ? 'var(--accent)' : 'var(--glass-border)' 
                      }}
                    />
                    <div 
                      onClick={() => setActiveField(activeField === f.id ? null : f.id)}
                      style={{ 
                        position: 'absolute', 
                        right: 12, 
                        top: 26, 
                        fontSize: '0.9rem', 
                        cursor: 'pointer',
                        color: activeField === f.id ? 'var(--accent)' : 'var(--text-muted)'
                      }}
                    >
                      {activeField === f.id ? '🎯' : '📐'}
                    </div>
                  </div>
                ))}
             </div>
          </section>

          {/* Categorical Selections */}
          <section>
            <h4 style={{ fontSize: '0.65rem', opacity: 0.5, letterSpacing: '0.1em', marginBottom: 12 }}>SYNAPSE CATEGORIES</h4>
            <div style={{ display: 'grid', gap: '1.5rem' }}>
              {Object.entries(OPTIONS).map(([field, vals]) => (
                <div key={field} className="form-group">
                  <label style={{ fontSize: '0.6rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--accent)', marginBottom: 8, display: 'block' }}>
                    {LABELS[field]}
                  </label>
                  <div className="neural-bubble-group">
                    {vals.map(v => (
                      <button
                        key={v}
                        className={`neural-bubble ${selections[field] === v ? 'active' : ''}`}
                        onClick={() => handleSelect(field, v)}
                      >
                        {v.replace(/_/g, ' ')}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>

        <div style={{ marginTop: 'auto', paddingTop: '2.5rem', display: 'flex', gap: 12 }}>
          <button 
            className="auth-btn" 
            onClick={handleSubmit} 
            disabled={loading}
            style={{ flex: 2, height: 50 }}
          >
            {loading ? 'SYNCHRONIZING...' : 'COMMIT & NEXT'}
          </button>
          <button 
            className="auth-btn" 
            onClick={handleRetrain} 
            disabled={loading}
            style={{ flex: 1, height: 50, background: 'rgba(255,255,255,0.05)', color: 'var(--text-muted)' }}
          >
            OPTIMIZE
          </button>
        </div>
      </div>

      {/* Viewport Column (Physical Audit) */}
      <div style={{ height: '100%' }}>
        <ImperialViewport 
          file={file} 
          activeField={activeField}
          onRoiExtracted={handleRoiExtracted}
        />
      </div>

    </div>
  )
}
