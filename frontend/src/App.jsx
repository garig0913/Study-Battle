import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom'
import Workspace from './pages/Workspace'
import Matches from './pages/Matches'
import Arena from './pages/Arena'

function Navigation() {
  const location = useLocation()
  return (
    <nav className="nav">
      <Link to="/" className={location.pathname === '/' ? 'active' : ''}>
        Workspace
      </Link>
      <Link to="/matches" className={location.pathname === '/matches' ? 'active' : ''}>
        Matches
      </Link>
    </nav>
  )
}

function HomeButton() {
  return (
    <Link to="/" className="home-button" title="Home">
      Home
    </Link>
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
        <HomeButton />
        <Routes>
          <Route path="/" element={<><Navigation /><Workspace /></>} />
          <Route path="/matches" element={<><Navigation /><Matches /></>} />
          <Route path="/arena/:matchId" element={<Arena />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}

export default App
