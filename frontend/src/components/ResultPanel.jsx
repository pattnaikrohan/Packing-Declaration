export default function ResultPanel({ ruleOutcomes, mlBonus, mlActive }) {
  const sev = (s) => s.toLowerCase()

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div className="section-divider" style={{ margin: '0.5rem 0' }} />
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {ruleOutcomes.map((r) => (
          <div key={r.rule_id} className="insight-box" style={{ 
            borderLeft: `4px solid var(--${r.severity === 'FAIL' ? 'amber-text' : r.severity === 'ERROR' ? 'amber-text' : 'green-text'})`,
            background: 'var(--field-bg)',
            padding: '1rem',
            alignItems: 'flex-start',
            gap: '1rem'
          }}>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span className="badge" style={{ 
                  fontSize: '0.65rem', 
                  background: r.severity === 'FAIL' ? 'var(--amber-bg)' : 'var(--green-bg)',
                  color: r.severity === 'FAIL' ? 'var(--amber-text)' : 'var(--green-text)'
                }}>
                  {r.severity}
                </span>
                <span style={{ fontSize: '0.75rem', fontWeight: 700, opacity: 0.8 }}>{r.rule_id}</span>
              </div>
              <div style={{ fontSize: '0.85rem', lineHeight: 1.4 }}>{r.message}</div>
              {r.fix && (
                <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: 'var(--accent)', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span>💡</span>
                  <i>{r.fix}</i>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* 
      <div className="insight-box" style={{ background: 'var(--bg-grad-3)', border: '1px solid var(--accent-glow)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: '1.5rem' }}>🤖</span>
          <div>
            <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.05em', opacity: 0.6 }}>ML Logic Adjustment</div>
            <div style={{ fontSize: '0.9rem', fontWeight: 700 }}>
              {mlActive ? (
                <span>{mlBonus >= 0 ? '+' : ''}{mlBonus.toFixed(1)} pts</span>
              ) : (
                <span style={{ opacity: 0.5 }}>Inactive (Low Sample Size)</span>
              )}
            </div>
          </div>
        </div>
      </div>
      */}
    </div>
  )
}
