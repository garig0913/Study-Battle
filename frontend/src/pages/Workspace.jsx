import Upload from './Upload'
import Chatbot from './Chatbot'

function Workspace() {
  return (
    <div className="grid">
      <div className="card">
        <h2 style={{ marginBottom: '16px' }}>Upload & Course Setup</h2>
        <Upload />
      </div>
      <div className="card">
        <h2 style={{ marginBottom: '16px' }}>Assistant</h2>
        <Chatbot />
      </div>
    </div>
  )
}

export default Workspace
