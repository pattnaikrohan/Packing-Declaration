import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || (import.meta.env.PROD ? 'https://pkd-declaration.azurewebsites.net' : ''),
})

export default api

/**
 * Upload a packing declaration file.
 * Returns the extracted PackingDeclaration JSON.
 */
export async function uploadFile(file) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post('/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

/**
 * Clear all existing blobs from Azure Storage before starting a new batch.
 */
export async function clearStorage() {
  const { data } = await api.post('/upload/clear-storage')
  return data
}

/**
 * Submit the reviewed declaration JSON to Power Automate.
 */
export async function submitToPA(declarationJson) {
  const { data } = await api.post('/submit', declarationJson)
  return data
}

/**
 * Perform final external DAFF validation via Power Automate logic flow.
 */
export async function validateDaffExternal(data) {
  const url = "https://default9a3bb30112fd4106a7f7563f72cfdf.69.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/441c87ba0ccb46c4b4b17256e45ee5af/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=gLt0xaUPTjyuGt9Dslr5-xQd_Bb7PiBPgHVE4Bf1GIk";
  // We use standard fetch for external cross-origin flows to avoid axios interceptor issues
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      FileName: data.file_name || "Unknown",
      ExtractedData: data
    })
  });
  if (!response.ok) throw new Error('External validation failed');
  return await response.json();
}

/**
 * Trigger neural model training on the backend.
 */
export async function trainModel() {
  const { data } = await api.post('/upload/train')
  return data
}

/**
 * Fetch ML performance metrics and intelligence stats.
 */
export async function getMLStats() {
  const { data } = await api.get('/upload/ml-stats')
  return data
}

/**
 * Submit a file and its human-verified labels to the training corpus.
 */
export async function submitLabelledFile(file, labels) {
  const form = new FormData()
  form.append('file', file)
  form.append('labels_json', JSON.stringify(labels))
  const { data } = await api.post('/upload/label', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

/**
 * Extract text from a document ROI (Region of Interest).
 */
export async function extractROI(file, x1, y1, x2, y2) {
  const form = new FormData()
  form.append('file', file)
  form.append('x1', x1)
  form.append('y1', y1)
  form.append('x2', x2)
  form.append('y2', y2)
  const { data } = await api.post('/upload/roi-extract', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data.text
}

/**
 * Bulk upload files for training with a single categorical label.
 */
export async function trainingUpload(files, labelType) {
  const form = new FormData()
  files.forEach(f => form.append('files', f))
  form.append('label_type', labelType)
  const { data } = await api.post('/upload/bulk', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

/**
 * List all background training and optimization jobs.
 */
export async function listTrainingJobs() {
  const { data } = await api.get('/upload/jobs')
  return data
}

/**
 * Trigger Power Automate flow to email audit report violations.
 */
export async function emailAuditReport(email, fileName, errors) {
  const url = "https://default9a3bb30112fd4106a7f7563f72cfdf.69.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/052d8326f1c44497b4d468ea183a42ed/triggers/manual/paths/invoke?api-version=1";
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email: email,
      fileName: fileName,
      errors: errors.join('\n')
    })
  });
  if (!response.ok) throw new Error('Email trigger failed');
  return await response.json();
}
