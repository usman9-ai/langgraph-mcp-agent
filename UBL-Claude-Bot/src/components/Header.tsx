import React from 'react';
import { useStore } from '../store/useStore';
import { useNavigate } from 'react-router-dom';

const Header: React.FC = () => {
  const { currentConversation, createConversation, clearAuth } = useStore();
  const navigate = useNavigate();

  const handleLogout = () => {
    clearAuth();
    navigate('/login', { replace: true });
  };

  return (
    <header className="h-16 border-b border-border bg-secondary flex items-center justify-between px-6 backdrop-blur-sm sticky top-0 z-10 shadow-sm">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-accent to-accent-hover flex items-center justify-center shadow-sm text-white font-semibold">
          UBL
        </div>
        <div>
          <p className="text-sm font-semibold text-text-primary">UBL Tableau Analytics</p>
          <p className="text-xs text-text-secondary">{currentConversation?.title || 'New conversation'}</p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={createConversation}
          className="py-2.5 px-4 bg-accent hover:bg-accent-hover rounded-xl font-medium transition-all duration-200 flex items-center justify-center gap-2 shadow-sm hover:shadow-md transform hover:scale-[1.02] active:scale-[0.98] text-white"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          <span>New Chat</span>
        </button>

        <button
          onClick={handleLogout}
          className="py-2.5 px-4 bg-transparent border border-border hover:bg-hover rounded-xl font-medium transition-all duration-200 flex items-center justify-center gap-2 text-text-primary"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a2 2 0 01-2 2H6a2 2 0 01-2-2V7a2 2 0 012-2h5a2 2 0 012 2v1" />
          </svg>
          <span>Logout</span>
        </button>
      </div>
    </header>
  );
};

export default Header;
