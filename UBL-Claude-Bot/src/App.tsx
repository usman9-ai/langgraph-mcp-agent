import { Navigate, Routes, Route } from 'react-router-dom';
import ChatArea from './components/ChatArea';
import Header from './components/Header';
import Login from './pages/LoginPage';
import { useStore } from './store/useStore';

function HomePage() {
  return (
    <div className="flex flex-col h-screen bg-primary text-text-primary overflow-hidden">
      <Header />
      <div className="flex-1 flex flex-col overflow-hidden min-h-0">
        <ChatArea />
      </div>
    </div>
  );
}

function App() {
  const accessToken = useStore((state) => state.accessToken);

  return (
    <Routes>
      <Route
        path="/home"
        element={accessToken ? <HomePage /> : <Navigate to="/login" replace />}
      />
      <Route
        path="/login"
        element={accessToken ? <Navigate to="/home" replace /> : <Login />}
      />
      <Route
        path="/"
        element={<Navigate to={accessToken ? '/home' : '/login'} replace />}
      />
    </Routes>
  );
}

export default App;
