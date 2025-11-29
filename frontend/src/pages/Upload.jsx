import { useState, useRef, useEffect } from 'react'

function CourseFiles({ courseId }) {
  const [files, setFiles] = useState([])
  const [menuOpen, setMenuOpen] = useState(null)
  const [details, setDetails] = useState(null)
  useEffect(() => {
    const fetchFiles = async () => {
      try {
        const res = await fetch(`/api/course-files/${courseId}`)
        const data = await res.json()
        setFiles(data.files || [])
      } catch {}
    }
    fetchFiles()
  }, [courseId])
  const openUrl = (url) => {
    const full = new URL(url, window.location.origin).href
    window.open(full, '_blank')
  }
  const getDetails = async (saved_name) => {
    try {
      const res = await fetch(`/api/course-file-details/${courseId}/${saved_name}`)
      const data = await res.json()
      setDetails(data)
    } catch {}
  }
  const deleteFile = async (saved_name) => {
    try {
      await fetch(`/api/course-file/${courseId}/${saved_name}`, { method: 'DELETE' })
      setMenuOpen(null)
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('courses:refresh'))
      }
      const res = await fetch(`/api/course-files/${courseId}`)
      const data = await res.json()
      setFiles(data.files || [])
    } catch {}
  }
  if (!files || files.length === 0) return null
  return (
    <div style={{ display: 'grid', gap: '8px' }}>
      {files.map((f, idx) => (
        <div key={idx} className="file-row" style={{ display: 'grid', gridTemplateColumns: '1fr auto auto', alignItems: 'center', gap: '8px', padding: '8px', background: 'rgba(255,255,255,0.05)', borderRadius: '8px' }}>
          <div>
            <a
              className="inline-link"
              href={new URL(f.url, window.location.origin).href}
              target="_blank"
              rel="noopener noreferrer"
            >
              {f.file_name}
            </a>
            {typeof f.chunk_count === 'number' && (
              <span style={{ marginLeft: '8px', opacity: 0.7 }}>({f.chunk_count} chunks)</span>
            )}
          </div>
          <button className="btn-secondary" onClick={() => getDetails(f.saved_name)} style={{ padding: '6px 10px' }}>Details</button>
          <button className="btn-secondary" onClick={() => deleteFile(f.saved_name)} style={{ padding: '6px 10px' }}>Delete</button>
        </div>
      ))}
      {details && (
        <div className="card" style={{ width: '100%' }}>
          <h4>Details</h4>
          <p><strong>File:</strong> {details.file_name}</p>
          <p><strong>Size:</strong> {details.size_bytes} bytes</p>
          <p><strong>Pages:</strong> {details.page_count}</p>
          <p><strong>Chunks:</strong> {details.chunk_count}</p>
        </div>
      )}
    </div>
  )
}

function Upload() {
  const [files, setFiles] = useState([])
  const [uploading, setUploading] = useState(false)
  const [uploadResult, setUploadResult] = useState(null)
  const [error, setError] = useState(null)
  const fileInputRef = useRef(null)
  const [courses, setCourses] = useState([])
  const [successMsg, setSuccessMsg] = useState('')

  const handleFileSelect = (e) => {
    const selectedFiles = Array.from(e.target.files)
    setFiles(selectedFiles)
    setError(null)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    const droppedFiles = Array.from(e.dataTransfer.files)
    setFiles(droppedFiles)
    setError(null)
  }

  const handleDragOver = (e) => {
    e.preventDefault()
  }

  const handleUpload = async () => {
    if (files.length === 0) {
      setError('Please select at least one file')
      return
    }

    setUploading(true)
    setError(null)

    const formData = new FormData()
    files.forEach(file => {
      formData.append('files', file)
    })

    try {
      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        throw new Error('Upload failed')
      }

      const result = await response.json()
      setUploadResult(result)
      setFiles([])
      
      localStorage.setItem('lastCourseId', result.course_id)
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('courses:refresh'))
      }
      setSuccessMsg('Upload successful')
      setTimeout(() => setSuccessMsg(''), 3000)
    } catch (err) {
      setError(err.message || 'Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }

  useEffect(() => {
    const fetchCourses = async () => {
      try {
        const res = await fetch('/api/courses')
        const data = await res.json()
        setCourses(data.courses || [])
      } catch {}
    }
    fetchCourses()
    const handler = () => fetchCourses()
    window.addEventListener('courses:refresh', handler)
    return () => window.removeEventListener('courses:refresh', handler)
  }, [])

  return (
    <div>
      <div className="card">
        <h2>Upload Study Materials</h2>
        <p style={{ marginBottom: '20px', opacity: 0.7 }}>
          Upload PDF, DOCX, PPTX, TXT, or image files to create a study course.
        </p>

      <div 
        className="file-upload"
        onClick={() => fileInputRef.current?.click()}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
      >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.pptx,.txt,.png,.jpg,.jpeg"
            onChange={handleFileSelect}
            style={{ display: 'none' }}
          />
          <p style={{ fontSize: '18px', marginBottom: '10px' }}>
            Drop files here or click to browse
          </p>
          <p style={{ opacity: 0.5 }}>
            Supported: PDF, DOCX, PPTX, TXT, PNG, JPG
          </p>
        </div>

        {successMsg && (
          <p style={{ color: '#38ef7d', marginTop: '12px' }}>{successMsg}</p>
        )}

        {files.length > 0 && (
          <div className="file-list">
            <h3>Selected Files:</h3>
            {files.map((file, index) => (
              <div key={index} className="file-item">
                <span style={{ flex: 1 }}>{file.name}</span>
                <span style={{ opacity: 0.5 }}>{formatFileSize(file.size)}</span>
              </div>
            ))}
          </div>
        )}

        {error && (
          <p style={{ color: '#f45c43', marginTop: '20px' }}>{error}</p>
        )}

        <button 
          className="btn-primary" 
          onClick={handleUpload}
          disabled={uploading || files.length === 0}
          style={{ marginTop: '20px', width: '100%' }}
        >
          {uploading ? (
            <span className="loading">
              <span className="spinner"></span>
              Uploading...
            </span>
          ) : (
            'Upload Files'
          )}
        </button>
      </div>

      

      {courses.filter(c => (c.files && c.files.length > 0) && (c.chunk_count && c.chunk_count > 0)).length > 0 && (
        <div className="card">
          <h3>Uploaded Materials</h3>
          <div style={{ marginTop: '10px' }}>
            {courses.filter(c => (c.files && c.files.length > 0) && (c.chunk_count && c.chunk_count > 0)).map((c, i) => (
              <div key={i} style={{ marginBottom: '12px', opacity: 0.9 }}>
                <div style={{ marginBottom: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span><strong>Course:</strong> {c.files.length} file(s)</span>
                  <span style={{ opacity: 0.8 }}>{c.chunk_count} chunks total</span>
                </div>
                <CourseFiles courseId={c.course_id} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default Upload
