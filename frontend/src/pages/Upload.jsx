import { useState, useRef } from 'react'

function Upload() {
  const [files, setFiles] = useState([])
  const [uploading, setUploading] = useState(false)
  const [uploadResult, setUploadResult] = useState(null)
  const [error, setError] = useState(null)
  const fileInputRef = useRef(null)

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

      {uploadResult && (
        <div className="card" style={{ borderColor: '#38ef7d' }}>
          <h3 style={{ color: '#38ef7d' }}>Upload Successful!</h3>
          <p><strong>Course ID:</strong> {uploadResult.course_id}</p>
          <p><strong>Files:</strong> {uploadResult.files.join(', ')}</p>
          <p><strong>Chunks Indexed:</strong> {uploadResult.chunks_indexed}</p>
          <p style={{ marginTop: '20px', opacity: 0.7 }}>
            You can now create a match in the Lobby using this course.
          </p>
        </div>
      )}
    </div>
  )
}

export default Upload
