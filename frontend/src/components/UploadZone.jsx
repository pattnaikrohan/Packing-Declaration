import { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'

const ACCEPTED_TYPES = {
  'application/pdf': ['.pdf'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/png': ['.png'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
}

export default function UploadZone({ onFiles, multiple = false, label = 'Drop files here or click to browse' }) {
  const onDrop = useCallback((accepted) => {
    if (accepted.length > 0) onFiles(multiple ? accepted : accepted[0])
  }, [onFiles, multiple])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    multiple,
  })

  return (
    <div 
      {...getRootProps()} 
      className={`glass-panel ${isDragActive ? 'active' : ''}`}
      style={{ 
        border: '2px dashed var(--glass-border)', 
        padding: '3rem 2rem', 
        textAlign: 'center', 
        cursor: 'pointer',
        transition: 'all 0.3s ease',
        background: isDragActive ? 'var(--bg-grad-1)' : 'var(--glass-bg)',
        boxShadow: isDragActive ? 'var(--accent-glow) 0px 0px 20px' : 'none'
      }}
    >
      <input {...getInputProps()} />
      <div style={{ fontSize: 40, marginBottom: 16 }}>☁️</div>
      <div style={{ fontWeight: 600, fontSize: '1.1rem', marginBottom: 8, color: 'var(--text-main)' }}>
        {isDragActive ? 'Drop to Start Extraction' : label}
      </div>
      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
        PDF, DOCX, XLSX, JPG, PNG — max 20 MB
      </div>
    </div>
  )
}
