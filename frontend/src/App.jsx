import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom'
import Upload from './pages/Upload'
import Lobby from './pages/Lobby'
import Arena from './pages/Arena'

function Navigation() {
  const location = useLocation()
  
  return (
    <nav className="nav">
      <Link to="/" className={location.pathname === '/' ? 'active' : ''}>
        Upload
      </Link>
      <Link to="/lobby" className={location.pathname === '/lobby' ? 'active' : ''}>
        Lobby
      </Link>
    </nav>
  )
}

function App() {
  return (
    <BrowserRouter>
      <div className="container">
        <h1 style={{ textAlign: 'center', marginBottom: '10px' }}>Study Battle</h1>
        <p style={{ textAlign: 'center', marginBottom: '30px', opacity: 0.7 }}>
          Competitive learning powered by RAG
        </p>
        <Routes>
          <Route path="/" element={<><Navigation /><Upload /></>} />
          <Route path="/lobby" element={<><Navigation /><Lobby /></>} />
          <Route path="/arena/:matchId" element={<Arena />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}

export default App
