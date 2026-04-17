import { useState, useEffect } from 'react';
import GameHeader from './components/GameHeader';
import GameTabs from './components/GameTabs';
import Toast from './components/Toast';
import useGameState from './hooks/useGameState';
import { ThemeProvider } from './theme';
import './App.css';

function AppContent() {
  const { gameState, loading, error, refresh } = useGameState();
  const [toasts, setToasts] = useState([]);

  const addToast = (message, type = 'info') => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 3000);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
          <p className="mt-4 text-gray-600">Loading game state...</p>
        </div>
      </div>
    );
  }

  if (error && !gameState) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-red-600 mb-4">Connection Error</h2>
          <p className="text-gray-600 mb-4">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="px-6 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100">
      <GameHeader gameState={gameState} onRefresh={refresh} />
      {gameState && <GameTabs gameState={gameState} onRefresh={refresh} onToast={addToast} />}
      <Toast toasts={toasts} />
    </div>
  );
}

function App() {
  return (
    <ThemeProvider>
      <AppContent />
    </ThemeProvider>
  );
}

export default App;
