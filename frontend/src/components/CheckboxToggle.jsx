/**
 * Tri-state toggle: YES | NO | BLANK
 * or binary toggle: PRESENT | ABSENT
 */
export default function CheckboxToggle({ value, onChange, options }) {
  return (
    <div className="tri-toggle">
      {options.map(({ label, val, cls }) => (
        <button
          key={val}
          type="button"
          className={`tri-toggle-opt ${cls}${value === val ? ' active' : ''}`}
          onClick={() => onChange(val)}
        >
          {label}
        </button>
      ))}
    </div>
  )
}

export const TRI_YES_NO = [
  { label: 'YES', val: 'YES', cls: 'yes' },
  { label: 'NO', val: 'NO', cls: 'no' },
  { label: 'BLANK', val: 'BLANK', cls: 'blank' },
]

export const BINARY_PRESENT = [
  { label: 'PRESENT', val: 'PRESENT', cls: 'yes' },
  { label: 'ABSENT', val: 'ABSENT', cls: 'no' },
]
