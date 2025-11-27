import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'

function Arena() {
  const { matchId: rawMatchId } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const matchId = rawMatchId.split('?')[0]
  const playerName = searchParams.get('player') || localStorage.getItem('playerName') || 'Player'
  
  const [connected, setConnected] = useState(false)
  const [matchReady, setMatchReady] = useState(false)
  const [players, setPlayers] = useState({})
  const [currentQuestion, setCurrentQuestion] = useState(null)
  const [timeLeft, setTimeLeft] = useState(0)
  const [answer, setAnswer] = useState('')
  const [selectedOption, setSelectedOption] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [roundResult, setRoundResult] = useState(null)
  const [matchEnd, setMatchEnd] = useState(null)
  const [error, setError] = useState(null)
  const [cooldown, setCooldown] = useState(0)
  const [waitingForOpponent, setWaitingForOpponent] = useState(true)
  
  const wsRef = useRef(null)
  const cooldownTimerRef = useRef(null)

  const connectWebSocket = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws/${matchId}?player=${encodeURIComponent(playerName)}`
    
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      console.log('WebSocket connected')
      setConnected(true)
      setError(null)
    }

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data)
      console.log('Received:', message)
      handleMessage(message)
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      setError('Connection error')
    }

    ws.onclose = () => {
      console.log('WebSocket closed')
      setConnected(false)
    }

    return ws
  }, [matchId, playerName])

  useEffect(() => {
    const ws = connectWebSocket()
    return () => {
      if (ws) ws.close()
    }
  }, [connectWebSocket])

  useEffect(() => {
    if (cooldown > 0) {
      cooldownTimerRef.current = setInterval(() => {
        setCooldown(c => Math.max(0, c - 1))
      }, 1000)
    } else {
      if (cooldownTimerRef.current) {
        clearInterval(cooldownTimerRef.current)
      }
    }
    return () => {
      if (cooldownTimerRef.current) {
        clearInterval(cooldownTimerRef.current)
      }
    }
  }, [cooldown])

  const handleMessage = (message) => {
    const { type, data } = message

    switch (type) {
      case 'connected':
        console.log('Connected as', data.player)
        break

      case 'match_ready':
        setMatchReady(true)
        setWaitingForOpponent(false)
        setPlayers(data.players)
        break

      case 'round_start':
        setCurrentQuestion(data)
        setTimeLeft(data.time_limit)
        setAnswer('')
        setSelectedOption(null)
        setRoundResult(null)
        setSubmitting(false)
        break

      case 'round_update':
        setTimeLeft(data.seconds_left)
        break

      case 'round_result':
        setRoundResult(data)
        setCurrentQuestion(null)
        if (data.players) {
          setPlayers(data.players)
        }
        break

      case 'answer_feedback':
        if (!data.correct) {
          setCooldown(data.cooldown_seconds || 2)
          setError(data.explanation)
          setTimeout(() => setError(null), 3000)
        }
        setSubmitting(false)
        break

      case 'match_end':
        setMatchEnd(data)
        if (data.final_hp) {
          setPlayers(Object.fromEntries(
            Object.entries(data.final_hp).map(([name, hp]) => [name, { hp }])
          ))
        }
        break

      case 'error':
        setError(data.message)
        break

      default:
        console.log('Unknown message type:', type)
    }
  }

  const submitAnswer = () => {
    if (!wsRef.current || submitting || cooldown > 0) return
    
    const answerPayload = currentQuestion.question_type === 'mcq' 
      ? selectedOption 
      : answer

    if (!answerPayload) {
      setError('Please provide an answer')
      return
    }

    setSubmitting(true)
    setError(null)

    wsRef.current.send(JSON.stringify({
      type: 'submit_answer',
      data: {
        question_id: currentQuestion.question_id,
        answer: answerPayload
      }
    }))
  }

  const getHealthBarClass = (hp) => {
    if (hp > 60) return 'high'
    if (hp > 30) return 'medium'
    return 'low'
  }

  const getTimerClass = () => {
    if (timeLeft <= 5) return 'danger'
    if (timeLeft <= 10) return 'warning'
    return ''
  }

  if (matchEnd) {
    return (
      <div className="ko-screen">
        <div className="ko-text">K.O.</div>
        <div className="winner-text">
          {matchEnd.winner === playerName ? 'You Win!' : `${matchEnd.winner} Wins!`}
        </div>
        <div style={{ marginTop: '30px' }}>
          {Object.entries(matchEnd.final_hp || {}).map(([name, hp]) => (
            <p key={name} style={{ fontSize: '20px', marginBottom: '10px' }}>
              {name}: {hp} HP
            </p>
          ))}
        </div>
        <button 
          className="btn-primary" 
          onClick={() => navigate('/lobby')}
          style={{ marginTop: '30px' }}
        >
          Back to Lobby
        </button>
      </div>
    )
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h2>Match: {matchId}</h2>
        <span className={`status-badge ${matchReady ? 'active' : 'waiting'}`}>
          {matchReady ? 'Battle!' : 'Waiting...'}
        </span>
      </div>

      {!connected && (
        <div className="card" style={{ textAlign: 'center' }}>
          <div className="loading">
            <div className="spinner"></div>
            <span>Connecting...</span>
          </div>
        </div>
      )}

      {connected && waitingForOpponent && !matchReady && (
        <div className="card" style={{ textAlign: 'center' }}>
          <h3>Waiting for opponent...</h3>
          <p style={{ opacity: 0.7, marginTop: '10px' }}>
            Share match ID: <strong>{matchId}</strong>
          </p>
          <div className="loading" style={{ marginTop: '20px' }}>
            <div className="spinner"></div>
          </div>
        </div>
      )}

      {Object.keys(players).length > 0 && (
        <div className="card">
          <h3 style={{ marginBottom: '16px' }}>Players</h3>
          {Object.entries(players).map(([name, data]) => (
            <div key={name} className="health-bar-container">
              <span className="player-name">
                {name === playerName ? `${name} (You)` : name}
              </span>
              <div className="health-bar">
                <div 
                  className={`health-bar-fill ${getHealthBarClass(data.hp)}`}
                  style={{ width: `${data.hp}%` }}
                />
              </div>
              <span className="hp-text">{data.hp} HP</span>
            </div>
          ))}
        </div>
      )}

      {currentQuestion && (
        <>
          <div className={`timer ${getTimerClass()}`}>
            {timeLeft}s
          </div>

          <div className="question-card">
            <div className="question-text">
              {currentQuestion.question_text}
            </div>

            {currentQuestion.question_type === 'mcq' && currentQuestion.options ? (
              <div className="options-list">
                {currentQuestion.options.map((option, index) => (
                  <button
                    key={index}
                    className={`option-btn ${selectedOption === option.charAt(0) ? 'selected' : ''}`}
                    onClick={() => setSelectedOption(option.charAt(0))}
                    disabled={submitting || cooldown > 0}
                  >
                    {option}
                  </button>
                ))}
              </div>
            ) : currentQuestion.question_type === 'code' ? (
              <textarea
                className="answer-input"
                placeholder="Enter your code..."
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                rows={6}
                disabled={submitting || cooldown > 0}
              />
            ) : (
              <input
                type="text"
                className="answer-input"
                placeholder="Enter your answer..."
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && submitAnswer()}
                disabled={submitting || cooldown > 0}
              />
            )}

            {error && (
              <p style={{ color: '#f45c43', marginTop: '16px' }}>{error}</p>
            )}

            {cooldown > 0 && (
              <p style={{ color: '#ffd200', marginTop: '16px' }}>
                Cooldown: {cooldown}s
              </p>
            )}

            <button
              className="btn-success"
              onClick={submitAnswer}
              disabled={submitting || cooldown > 0 || (!answer && !selectedOption)}
              style={{ width: '100%', marginTop: '20px' }}
            >
              {submitting ? 'Submitting...' : 'Submit Answer'}
            </button>
          </div>
        </>
      )}

      {roundResult && (
        <div className="result-overlay" onClick={() => setRoundResult(null)}>
          <div className="result-card" onClick={(e) => e.stopPropagation()}>
            {roundResult.timeout ? (
              <>
                <div className="result-title" style={{ color: '#ffd200' }}>
                  Time's Up!
                </div>
                <p>Both players take {roundResult.damage} damage</p>
              </>
            ) : roundResult.winner_player === playerName ? (
              <>
                <div className="result-title winner">Correct!</div>
                <p>You dealt {roundResult.damage} damage in {roundResult.time_taken}s</p>
              </>
            ) : (
              <>
                <div className="result-title loser">
                  {roundResult.winner_player} answered first!
                </div>
                <p>They dealt {roundResult.damage} damage to you</p>
              </>
            )}

            <div className="solution-section">
              <h4>Solution:</h4>
              <p style={{ marginTop: '10px' }}>{roundResult.solution}</p>
              <p style={{ marginTop: '10px' }}>
                <strong>Answer:</strong> {roundResult.correct_answer}
              </p>
              
              {roundResult.citation && roundResult.citation.length > 0 && (
                <div className="citation">
                  <strong>Source:</strong>{' '}
                  {roundResult.citation.map((c, i) => (
                    <span key={i}>
                      {c.file_name} (Page {c.page})
                      {i < roundResult.citation.length - 1 ? ', ' : ''}
                    </span>
                  ))}
                </div>
              )}
            </div>

            <button 
              className="btn-secondary" 
              onClick={() => setRoundResult(null)}
              style={{ marginTop: '20px' }}
            >
              Continue
            </button>
          </div>
        </div>
      )}

      {matchReady && !currentQuestion && !roundResult && !matchEnd && (
        <div className="card" style={{ textAlign: 'center' }}>
          <div className="loading">
            <div className="spinner"></div>
            <span>Generating next question...</span>
          </div>
        </div>
      )}
    </div>
  )
}

export default Arena
