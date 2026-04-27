import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import toast from 'react-hot-toast'
import { trainingUpload } from '../api/client'

function formatBytes(b) {
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b/1024).toFixed(1)} KB`
  return `${(b/1024/1024).toFixed(1)} MB`
}

const ACCEPTED = {
  'application/pdf': ['.pdf'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/png': ['.png'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
}

export default function TrainingUploadQueue({ onJobQueued }) {
  const [label, setLabel] = useState(null)    // 'accepted' | 'rejected'
  const [files, setFiles] = useState([])
  const [uploading, setUploading] = useState(false)

  const onDrop = useCallback((accepted) => {
    setFiles((prev) => [...prev, ...accepted])
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED,
    multiple: true,
  })

  function removeFile(idx) {
    setFiles((prev) => prev.filter((_, i) => i !== idx))
  }

  async function handleUpload() {
    if (!label || files.length === 0) return
    setUploading(true)
    try {
      const result = await trainingUpload(files, label)
      toast.success(`${files.length} file${files.length > 1 ? 's' : ''} queued for training`)
      setFiles([])
      setLabel(null)
      onJobQueued?.(result)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const canUpload = label && files.length > 0 && !uploading

  return (
    <div className="glass-panel" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <h2 className="panel-title" style={{ fontSize: '1.2rem', marginBottom: '1rem' }}>
        <span className="glow-text">Bulk Optimization</span>
      </h2>
      <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '1.5rem', lineHeight: 1.5 }}>
        Upload large batches of accepted or rejected declarations to train the neural matrix in the background.
      </p>

      {/* Label selector */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
        <button
          className={`neural-bubble ${label === 'accepted' ? 'active' : ''}`}
          onClick={() => setLabel('accepted')}
          style={{ flex: 1 }}
        >
          ✅ Accepted
        </button>
        <button
          className={`neural-bubble ${label === 'rejected' ? 'active' : ''}`}
          onClick={() => setLabel('rejected')}
          style={{ flex: 1 }}
        >
          ❌ Rejected
        </button>
      </div>

      {/* Dropzone */}
      <div {...getRootProps()} className={`dropzone${isDragActive ? ' active' : ''}`} style={{ border: '2px dashed var(--glass-border)', borderRadius: 12, padding: 32, textAlign: 'center', background: 'rgba(255,255,255,0.02)', cursor: 'pointer' }}>
        <input {...getInputProps()} />
        <span style={{ fontSize: 32, display: 'block', marginBottom: 12 }}>📤</span>
        <div style={{ fontSize: '0.9rem', color: 'var(--text-main)', fontWeight: 600 }}>
          {isDragActive ? 'Release to queue' : 'Drop batch files here'}
        </div>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4 }}>PDF, DOCX, XLSX, Image</div>
      </div>

      {/* File list */}
      {files.length > 0 && (
        <div style={{ marginTop: 20, maxHeight: 150, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8 }}>
          {files.map((f, i) => (
            <div key={`${f.name}-${i}`} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(255,255,255,0.03)', padding: '8px 12px', borderRadius: 8, fontSize: '0.8rem' }}>
              <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '70%' }}>📄 {f.name}</span>
              <button onClick={() => removeFile(i)} style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer' }}>✕</button>
            </div>
          ))}
        </div>
      )}

      <div style={{ marginTop: 'auto', paddingTop: 20 }}>
        <button
          className="auth-btn"
          disabled={!canUpload}
          onClick={handleUpload}
          style={{ height: 50 }}
        >
          {uploading
            ? <><div className="loader" style={{ width: 14, height: 14, margin: 0, borderSize: 2 }} /> Processing...</>
            : files.length > 0 && label
              ? `Queue ${files.length} Samples`
              : 'Queue for Training'}
        </button>
      </div>
    </div>
  )
}
