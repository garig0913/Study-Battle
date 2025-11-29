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
  const [roundHistory, setRoundHistory] = useState([])
  const [skipStatus, setSkipStatus] = useState({})
  const [wsError, setWsError] = useState(null)
  
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
      setWsError(null)
    }

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data)
      console.log('Received:', message)
      handleMessage(message)
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      setError('Connection error')
      setWsError('WebSocket connection failed. Ensure you entered Arena via Matches and the backend is running.')
    }

    ws.onclose = () => {
      console.log('WebSocket closed')
      setConnected(false)
      if (!matchEnd) {
        setWsError('Connection closed')
      }
    }

    return ws
  }, [matchId, playerName])

  const retryConnect = () => {
    try {
      if (wsRef.current) wsRef.current.close()
    } catch {}
    setWsError(null)
    connectWebSocket()
  }

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
        setSkipStatus({})
        // Store the question for history
        setRoundHistory(prev => [...prev, {
          question_id: data.question_id,
          question_text: data.question_text,
          question_type: data.question_type,
          options: data.options,
          citation: data.citation || []
        }])
        break

      case 'round_update':
        setTimeLeft(data.seconds_left)
        break

      case 'skip_update':
        const skipped = {}
        ;(data.skipped_by || []).forEach(name => { skipped[name] = true })
        setSkipStatus(skipped)
        break

      case 'round_result':
        setRoundResult(data)
        setCurrentQuestion(null)
        if (data.players) {
          setPlayers(data.players)
        }
        setRoundHistory(prev => {
          if (prev.length === 0) return prev
          const updated = [...prev]
          updated[updated.length - 1] = {
            ...updated[updated.length - 1],
            solution: data.solution,
            correct_answer: data.correct_answer,
            citation: data.citation || updated[updated.length - 1].citation || []
          }
          return updated
        })
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
      <div style={{ maxHeight: '90vh', overflowY: 'auto' }}>
        <div className="ko-screen" style={{ marginBottom: '40px' }}>
          <div className="ko-text">K.O.</div>
          <div className="winner-text">
            {matchEnd.winner === playerName ? 'You Win!' : `${matchEnd.winner} Wins!`}
          </div>
          <div style={{ marginTop: '30px', marginBottom: '40px' }}>
            {Object.entries(matchEnd.final_hp || {}).map(([name, hp]) => (
              <p key={name} style={{ fontSize: '20px', marginBottom: '10px' }}>
                {name}: {hp} HP
              </p>
            ))}
          </div>
        </div>

        <div style={{ marginTop: '40px', marginBottom: '40px' }}>
          <h2 style={{ marginBottom: '20px', textAlign: 'center' }}>Problems & Sources</h2>
          {roundHistory.length > 0 ? (
            <div style={{ display: 'grid', gap: '20px' }}>
              {roundHistory.map((round, idx) => (
                <div key={idx} className="card" style={{ borderLeft: '4px solid #7c3aed' }}>
                  <div style={{ marginBottom: '12px' }}>
                    <span style={{ fontSize: '14px', opacity: 0.6 }}>Question {idx + 1}</span>
                    <h4 style={{ margin: '8px 0 12px 0' }}>{round.question_text}</h4>
                  </div>
                  
                  {round.options && (
                    <div style={{ marginBottom: '12px', fontSize: '14px', opacity: 0.8 }}>
                      <p style={{ margin: '0 0 6px 0' }}>
                        <strong>Options:</strong> {round.options.join(', ')}
                      </p>
                    </div>
                  )}

              {round.citation && round.citation.length > 0 && (
                <div style={{ 
                  padding: '12px', 
                  background: 'rgba(124, 58, 237, 0.1)', 
                  borderRadius: '8px',
                  marginTop: '12px'
                }}>
                  <strong style={{ fontSize: '14px' }}>📚 Source:</strong>
                  <div style={{ marginTop: '8px', fontSize: '14px' }}>
                    {round.citation.map((c, i) => (
                      c.url ? (
                        <div key={i} style={{ marginBottom: '4px', opacity: 0.9 }}>
                          <a href={c.url} target="_blank" rel="noopener noreferrer" className="inline-link">
                            {c.file_name} {c.page && `(Page ${c.page})`}
                          </a>
                        </div>
                      ) : (
                        <div key={i} style={{ marginBottom: '4px', opacity: 0.9 }}>
                          {c.file_name} {c.page && `(Page ${c.page})`}
                        </div>
                      )
                    ))}
                  </div>
                </div>
              )}

              {(round.solution || round.correct_answer) && (
                <div style={{ 
                  padding: '12px', 
                  background: 'rgba(255,255,255,0.05)', 
                  borderRadius: '8px',
                  marginTop: '12px'
                }}>
                  <strong style={{ fontSize: '14px' }}>Solution:</strong>
                  {round.solution && (
                    <p style={{ marginTop: '8px', fontSize: '14px' }}>{round.solution}</p>
                  )}
                  {round.correct_answer && (
                    <p style={{ marginTop: '8px', fontSize: '14px' }}>
                      <strong>Answer:</strong> {round.correct_answer}
                    </p>
                  )}
                </div>
              )}
                </div>
              ))}
            </div>
          ) : (
            <p style={{ textAlign: 'center', opacity: 0.6 }}>No problems in this match</p>
          )}
        </div>

        <div style={{ textAlign: 'center', marginTop: '40px', marginBottom: '40px' }}>
          <button 
            className="btn-primary" 
            onClick={() => navigate('/matches')}
          >
            Back to Lobby
          </button>
        </div>
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
          {wsError && (
            <p style={{ marginTop: '12px', opacity: 0.8 }}>{wsError}</p>
          )}
          <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', marginTop: '16px' }}>
            <button className="btn-secondary" onClick={retryConnect}>Retry</button>
            <button className="btn-primary" onClick={() => navigate('/matches')}>Back to Matches</button>
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
                {name === playerName ? `${name} (You)` : name}{skipStatus[name] ? ' • Skip' : ''}
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
            {skipStatus[playerName] && (
              <p style={{ marginTop: '8px', color: '#ffd200' }}>
                You opted to skip. {Object.keys(skipStatus).filter(n => n !== playerName).length === 0 ? 'Waiting for opponent...' : 'Opponent also opted to skip.'}
              </p>
            )}

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

            <button
              className="btn-secondary"
              onClick={() => wsRef.current && wsRef.current.send(JSON.stringify({ type: 'skip_round' }))}
              disabled={submitting || skipStatus[playerName]}
              style={{ width: '100%', marginTop: '10px' }}
            >
              {skipStatus[playerName] ? 'Skipped' : 'Skip Round'}
            </button>
          </div>
        </>
      )}

      {roundResult && (
        <div className="result-overlay" onClick={() => setRoundResult(null)}>
          <div className="result-card" onClick={(e) => e.stopPropagation()}>
            {roundResult.skipped ? (
              <>
                <div className="result-title" style={{ color: '#667eea' }}>
                  Round Skipped
                </div>
                <p>No damage dealt</p>
              </>
            ) : roundResult.timeout ? (
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
                    c.url ? (
                      <a key={i} href={c.url} target="_blank" rel="noopener noreferrer" className="inline-link">
                        {c.file_name} (Page {c.page})
                      </a>
                    ) : (
                      <span key={i}>{c.file_name} (Page {c.page})</span>
                    )
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
