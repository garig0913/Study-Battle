import { useEffect, useState, useCallback } from 'react'

function Chatbot() {
  const [messages, setMessages] = useState([
    { role: 'assistant', text: 'Hello. Ask about your uploaded courses or type help.' }
  ])
  const [input, setInput] = useState('')
  const [courses, setCourses] = useState([])

  const fetchCourses = useCallback(async () => {
    try {
      const res = await fetch('/api/courses')
      const data = await res.json()
      setCourses(data.courses || [])
    } catch {}
  }, [])

  useEffect(() => {
    fetchCourses()
    const handler = () => fetchCourses()
    window.addEventListener('courses:refresh', handler)
    return () => window.removeEventListener('courses:refresh', handler)
  }, [fetchCourses])

  const sendMessage = async () => {
    const q = input.trim()
    if (!q) return
    const userMsg = { role: 'user', text: q }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    const lower = q.toLowerCase()
    if (lower === 'help') {
      const reply = 'Ask questions about your uploaded materials. Type "courses" to list them.'
      setMessages(prev => [...prev, { role: 'assistant', text: reply }])
      setInput('')
      return
    }
    if (lower.startsWith('courses')) {
      const reply = courses.length === 0 ? 'No courses available.' : `Courses: ${courses.map(c => `${c.files.join(', ')} (${c.chunk_count} chunks)`).join(' | ')}`
      setMessages(prev => [...prev, { role: 'assistant', text: reply }])
      setInput('')
      return
    }
    const courseId = localStorage.getItem('lastCourseId')
    if (!courseId) {
      setMessages(prev => [...prev, { role: 'assistant', text: 'No course selected. Upload a file first.' }])
      setInput('')
      return
    }
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ course_id: courseId, question: q })
      })
      const data = await res.json()
      if (!res.ok) {
        const detail = data && (data.detail || data.message)
        setMessages(prev => [...prev, { role: 'assistant', text: detail || 'Error getting answer.' }])
        setInput('')
        return
      }
      let text = data.answer || 'No answer'
      if (Array.isArray(data.citation) && data.citation.length > 0) {
        const src = data.citation.map(c => `${c.file_name}${c.page ? ` (Page ${c.page})` : ''}`).join(', ')
        text += `\nSources: ${src}`
      }
      setMessages(prev => [...prev, { role: 'assistant', text }])
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', text: 'Error getting answer.' }])
    }
    setInput('')
  }

  return (
    <div>
      <div className="card">
        <h3 style={{ marginBottom: '12px' }}>Assistant</h3>
        <div style={{ maxHeight: '40vh', overflowY: 'auto', padding: '12px', background: 'rgba(255,255,255,0.05)', borderRadius: '8px' }}>
          {messages.map((m, i) => (
            <div key={i} style={{ marginBottom: '10px', opacity: m.role === 'assistant' ? 0.9 : 1 }}>
              <strong style={{ marginRight: '8px' }}>{m.role === 'assistant' ? 'Assistant:' : 'You:'}</strong>
              <span>{m.text}</span>
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', gap: '10px', marginTop: '12px' }}>
          <input
            type="text"
            className="answer-input"
            placeholder="Type a message..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
          />
          <button className="btn-primary" onClick={sendMessage}>Send</button>
        </div>
      </div>
    </div>
  )
}

export default Chatbot
