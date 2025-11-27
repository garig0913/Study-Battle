import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

function Lobby() {
  const navigate = useNavigate()
  const [courses, setCourses] = useState([])
  const [selectedCourse, setSelectedCourse] = useState('')
  const [playerName, setPlayerName] = useState('')
  const [timeLimit, setTimeLimit] = useState(30)
  const [difficulty, setDifficulty] = useState('medium')
  const [questionTypes, setQuestionTypes] = useState(['short', 'calc'])
  const [matchId, setMatchId] = useState('')
  const [joinMatchId, setJoinMatchId] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [createdMatch, setCreatedMatch] = useState(null)

  useEffect(() => {
    fetchCourses()
    const savedCourseId = localStorage.getItem('lastCourseId')
    if (savedCourseId) {
      setSelectedCourse(savedCourseId)
    }
  }, [])

  const fetchCourses = async () => {
    try {
      const response = await fetch('/api/courses')
      const data = await response.json()
      setCourses(data.courses || [])
    } catch (err) {
      console.error('Failed to fetch courses:', err)
    }
  }

  const handleCreateMatch = async () => {
    if (!selectedCourse || !playerName) {
      setError('Please select a course and enter your name')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const response = await fetch('/api/create-match', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          course_id: selectedCourse,
          player_name: playerName,
          time_limit_seconds: timeLimit,
          question_types: questionTypes,
          difficulty: difficulty,
        }),
      })

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || 'Failed to create match')
      }

      const data = await response.json()
      setCreatedMatch(data)
      localStorage.setItem('playerName', playerName)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleJoinMatch = async () => {
    if (!joinMatchId || !playerName) {
      setError('Please enter match ID and your name')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const response = await fetch('/api/join-match', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          match_id: joinMatchId,
          player_name: playerName,
        }),
      })

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || 'Failed to join match')
      }

      localStorage.setItem('playerName', playerName)
      navigate(`/arena/${joinMatchId}?player=${encodeURIComponent(playerName)}`)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleEnterArena = () => {
    if (createdMatch) {
      navigate(`/arena/${createdMatch.match_id}?player=${encodeURIComponent(playerName)}`)
    }
  }

  const toggleQuestionType = (type) => {
    if (questionTypes.includes(type)) {
      if (questionTypes.length > 1) {
        setQuestionTypes(questionTypes.filter(t => t !== type))
      }
    } else {
      setQuestionTypes([...questionTypes, type])
    }
  }

  return (
    <div className="grid">
      <div className="card">
        <h2>Create Match</h2>
        
        <label style={{ display: 'block', marginBottom: '8px', opacity: 0.7 }}>
          Your Name
        </label>
        <input
          type="text"
          placeholder="Enter your name"
          value={playerName}
          onChange={(e) => setPlayerName(e.target.value)}
        />

        <label style={{ display: 'block', marginBottom: '8px', opacity: 0.7 }}>
          Select Course
        </label>
        <select 
          value={selectedCourse} 
          onChange={(e) => setSelectedCourse(e.target.value)}
        >
          <option value="">Select a course...</option>
          {courses.map(course => (
            <option key={course.course_id} value={course.course_id}>
              {course.files.join(', ')} ({course.chunk_count} chunks)
            </option>
          ))}
        </select>

        <label style={{ display: 'block', marginBottom: '8px', opacity: 0.7 }}>
          Time Limit (seconds)
        </label>
        <input
          type="number"
          min="10"
          max="120"
          value={timeLimit}
          onChange={(e) => setTimeLimit(parseInt(e.target.value))}
        />

        <label style={{ display: 'block', marginBottom: '8px', opacity: 0.7 }}>
          Difficulty
        </label>
        <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
          <option value="easy">Easy</option>
          <option value="medium">Medium</option>
          <option value="hard">Hard</option>
        </select>

        <label style={{ display: 'block', marginBottom: '8px', opacity: 0.7 }}>
          Question Types
        </label>
        <div style={{ display: 'flex', gap: '10px', marginBottom: '16px', flexWrap: 'wrap' }}>
          {['mcq', 'short', 'calc', 'code'].map(type => (
            <button
              key={type}
              className={questionTypes.includes(type) ? 'btn-primary' : 'btn-secondary'}
              onClick={() => toggleQuestionType(type)}
              style={{ padding: '8px 16px' }}
            >
              {type.toUpperCase()}
            </button>
          ))}
        </div>

        {error && <p style={{ color: '#f45c43', marginBottom: '16px' }}>{error}</p>}

        <button 
          className="btn-success" 
          onClick={handleCreateMatch}
          disabled={loading}
          style={{ width: '100%' }}
        >
          {loading ? 'Creating...' : 'Create Match'}
        </button>

        {createdMatch && (
          <div style={{ marginTop: '20px', padding: '16px', background: 'rgba(56, 239, 125, 0.1)', borderRadius: '12px' }}>
            <p><strong>Match ID:</strong> {createdMatch.match_id}</p>
            <p style={{ opacity: 0.7, marginTop: '8px' }}>Share this ID with your opponent!</p>
            <button 
              className="btn-primary" 
              onClick={handleEnterArena}
              style={{ width: '100%', marginTop: '16px' }}
            >
              Enter Arena
            </button>
          </div>
        )}
      </div>

      <div className="card">
        <h2>Join Match</h2>
        
        <label style={{ display: 'block', marginBottom: '8px', opacity: 0.7 }}>
          Your Name
        </label>
        <input
          type="text"
          placeholder="Enter your name"
          value={playerName}
          onChange={(e) => setPlayerName(e.target.value)}
        />

        <label style={{ display: 'block', marginBottom: '8px', opacity: 0.7 }}>
          Match ID
        </label>
        <input
          type="text"
          placeholder="Enter match ID"
          value={joinMatchId}
          onChange={(e) => setJoinMatchId(e.target.value)}
        />

        <button 
          className="btn-primary" 
          onClick={handleJoinMatch}
          disabled={loading}
          style={{ width: '100%' }}
        >
          {loading ? 'Joining...' : 'Join Match'}
        </button>
      </div>
    </div>
  )
}

export default Lobby
