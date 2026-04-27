import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useForm, Controller } from 'react-hook-form'
import toast from 'react-hot-toast'
import CheckboxToggle, { TRI_YES_NO, BINARY_PRESENT } from '../components/CheckboxToggle'
import FieldError from '../components/FieldError'
import { validateDoc } from '../api/client'

const DECL_TYPES = ['FCL_ANNUAL', 'FCL_SINGLE', 'LCL_SINGLE', 'FCX_SINGLE']
const Q2_OPTS = [
  { label: 'YES (Timber)', val: 'YES_TIMBER' },
  { label: 'YES (Bamboo)', val: 'YES_BAMBOO' },
  { label: 'NO', val: 'NO' },
  { label: 'BLANK', val: 'BLANK' },
]
const Q3_OPTS = [
  { label: 'ISPM-15', val: 'ISPM15' },
  { label: 'DAFF Cert.', val: 'DAFF_CERTIFIED' },
  { label: 'Not Treated', val: 'NOT_TREATED' },
  { label: 'N/A', val: 'NOT_APPLICABLE' },
  { label: 'BLANK', val: 'BLANK' },
]

function Field({ label, children, error }) {
  return (
    <div className="field-group">
      <label className="field-label">{label}</label>
      {children}
      <FieldError message={error?.message} />
    </div>
  )
}

export default function ReviewPage() {
  const { state } = useLocation()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)

  const canonical = state?.canonical
  if (!canonical) {
    navigate('/')
    return null
  }

  const { register, handleSubmit, control, formState: { errors } } = useForm({
    defaultValues: {
      declaration_type: canonical.declaration_type || '',
      q1_unacceptable_material: canonical.q1_unacceptable_material || 'BLANK',
      q2_timber_bamboo: canonical.q2_timber_bamboo || 'BLANK',
      q3_treatment: canonical.q3_treatment || 'BLANK',
      q4_cleanliness: canonical.q4_cleanliness || 'ABSENT',
      alterations_present: canonical.alterations_present || false,
      alterations_endorsed: canonical.alterations_endorsed || false,
      // meta
      issuer_company: canonical.meta?.issuer_company || '',
      issuer_address: canonical.meta?.issuer_address || '',
      issuer_address_is_po_box: canonical.meta?.issuer_address_is_po_box || false,
      vessel_name: canonical.meta?.vessel_name || '',
      voyage_number: canonical.meta?.voyage_number || '',
      consignment_link: canonical.meta?.consignment_link || '',
      exporter: canonical.meta?.exporter || '',
      importer: canonical.meta?.importer || '',
      date_issued: canonical.meta?.date_issued || '',
      signed: canonical.meta?.signed || false,
      printed_name: canonical.meta?.printed_name || '',
      letterhead_present: canonical.meta?.letterhead_present || false,
    },
  })

  async function onSubmit(values) {
    setLoading(true)
    const doc = {
      ...canonical,
      declaration_type: values.declaration_type || null,
      q1_unacceptable_material: values.q1_unacceptable_material,
      q2_timber_bamboo: values.q2_timber_bamboo,
      q3_treatment: values.q3_treatment,
      q4_cleanliness: values.q4_cleanliness,
      alterations_present: values.alterations_present,
      alterations_endorsed: values.alterations_endorsed,
      meta: {
        ...canonical.meta,
        issuer_company: values.issuer_company || null,
        issuer_address: values.issuer_address || null,
        issuer_address_is_po_box: values.issuer_address_is_po_box,
        vessel_name: values.vessel_name || null,
        voyage_number: values.voyage_number || null,
        consignment_link: values.consignment_link || null,
        exporter: values.exporter || null,
        importer: values.importer || null,
        date_issued: values.date_issued || null,
        signed: values.signed,
        printed_name: values.printed_name || null,
        letterhead_present: values.letterhead_present,
      },
    }

    try {
      const result = await validateDoc(doc)
      navigate('/result', { state: { canonical: doc, result } })
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Validation failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h1 className="section-title">Review Extracted Data</h1>
        <p className="section-sub">
          Verify the extracted fields from <strong>{state?.fileName}</strong>. Correct anything that looks wrong before validating.
        </p>
        {canonical.extraction_method === 'ocr' && (
          <div style={{
            background: 'var(--color-warning-dim)',
            border: '1px solid rgba(245,158,11,0.3)',
            borderRadius: 'var(--radius-md)',
            padding: '10px 14px',
            fontSize: 13,
            color: 'var(--color-warning)',
            marginTop: 12,
          }}>
            ⚠️ OCR extraction (confidence: {(canonical.ocr_confidence * 100).toFixed(0)}%). Please verify fields carefully.
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit(onSubmit)}>
        {/* Declaration type */}
        <div className="card" style={{ marginBottom: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 14, color: 'var(--color-gold)' }}>Declaration Type</h3>
          <Field label="Declaration Type">
            <select className="field-input field-select" {...register('declaration_type')}>
              <option value="">Unknown / Not detected</option>
              {DECL_TYPES.map((t) => <option key={t} value={t}>{t.replace('_', ' ')}</option>)}
            </select>
          </Field>
        </div>

        {/* Meta fields */}
        <div className="card" style={{ marginBottom: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 14, color: 'var(--color-gold)' }}>Issuer & Parties</h3>
          <div className="form-grid">
            <Field label="Issuer Company"><input className="field-input" {...register('issuer_company')} /></Field>
            <Field label="Issuer Address (full)"><input className="field-input" {...register('issuer_address')} /></Field>
            <Field label="Exporter"><input className="field-input" {...register('exporter')} /></Field>
            <Field label="Importer"><input className="field-input" {...register('importer')} /></Field>
            <Field label="Vessel Name"><input className="field-input" {...register('vessel_name')} /></Field>
            <Field label="Voyage Number"><input className="field-input" {...register('voyage_number')} /></Field>
            <Field label="Consignment Link"><input className="field-input" {...register('consignment_link')} /></Field>
            <Field label="Date Issued (YYYY-MM-DD)"><input className="field-input" {...register('date_issued')} /></Field>
          </div>
          <div style={{ display: 'flex', gap: 24, marginTop: 14, flexWrap: 'wrap' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer' }}>
              <input type="checkbox" {...register('letterhead_present')} />
              Letterhead present
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer' }}>
              <input type="checkbox" {...register('issuer_address_is_po_box')} />
              Address is PO Box
            </label>
          </div>
        </div>

        {/* Signature */}
        <div className="card" style={{ marginBottom: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 14, color: 'var(--color-gold)' }}>Signature</h3>
          <div className="form-grid">
            <Field label="Printed Name"><input className="field-input" {...register('printed_name')} /></Field>
          </div>
          <div style={{ marginTop: 14 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer' }}>
              <input type="checkbox" {...register('signed')} />
              Signed
            </label>
          </div>
        </div>

        {/* Questions */}
        <div className="card" style={{ marginBottom: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 14, color: 'var(--color-gold)' }}>Compliance Questions</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <Field label="Q1 — Unacceptable Material">
              <Controller name="q1_unacceptable_material" control={control}
                render={({ field }) => <CheckboxToggle value={field.value} onChange={field.onChange} options={TRI_YES_NO} />} />
            </Field>
            <Field label="Q2 — Timber / Bamboo">
              <Controller name="q2_timber_bamboo" control={control}
                render={({ field }) => (
                  <CheckboxToggle value={field.value} onChange={field.onChange}
                    options={Q2_OPTS.map(o => ({ ...o, cls: o.val.startsWith('YES') ? 'yes' : o.val === 'NO' ? 'no' : 'blank' }))} />
                )} />
            </Field>
            <Field label="Q3 — Treatment">
              <Controller name="q3_treatment" control={control}
                render={({ field }) => (
                  <CheckboxToggle value={field.value} onChange={field.onChange}
                    options={Q3_OPTS.map(o => ({ ...o, cls: ['ISPM15','DAFF_CERTIFIED'].includes(o.val) ? 'yes' : o.val === 'BLANK' ? 'blank' : 'no' }))} />
                )} />
            </Field>
            <Field label="Q4 — Cleanliness">
              <Controller name="q4_cleanliness" control={control}
                render={({ field }) => <CheckboxToggle value={field.value} onChange={field.onChange} options={BINARY_PRESENT} />} />
            </Field>
          </div>
        </div>

        {/* Alterations */}
        <div className="card" style={{ marginBottom: 24 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 14, color: 'var(--color-gold)' }}>Alterations</h3>
          <div style={{ display: 'flex', gap: 24 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer' }}>
              <input type="checkbox" {...register('alterations_present')} />
              Alterations present
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer' }}>
              <input type="checkbox" {...register('alterations_endorsed')} />
              Alterations endorsed
            </label>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 12 }}>
          <button type="button" className="btn btn-secondary" onClick={() => navigate('/')}>← Back</button>
          <button type="submit" id="btn-validate" className="btn btn-primary btn-lg" style={{ flex: 1 }} disabled={loading}>
            {loading ? <><span className="spinner" /> Validating…</> : '→ Run Validation'}
          </button>
        </div>
      </form>
    </div>
  )
}
