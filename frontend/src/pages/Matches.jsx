import Lobby from './Lobby'

function Matches() {
  return (
    <div className="grid">
      <div className="card" style={{ width: '100%' }}>
        <h2 style={{ marginBottom: '16px' }}>Create or Join Match</h2>
        <Lobby />
      </div>
    </div>
  )
}

export default Matches
