import { RefreshCw, Moon, Sun, RotateCcw } from 'lucide-react';
import { useState } from 'react';
import { useTheme } from '../theme.jsx';
import { useAPI } from '../hooks/useAPI';
import { API_ENDPOINTS } from '../utils/constants';
import { formatCurrency } from '../utils/formatting';

const GameHeader = ({ gameState, onRefresh }) => {
  const { isDark, toggleTheme } = useTheme();
  const { request } = useAPI();
  const [refreshing, setRefreshing] = useState(false);
  const [showResetModal, setShowResetModal] = useState(false);
  const [resetting, setResetting] = useState(false);

  if (!gameState) return null;

  const { current_day, wallet_balance, warehouse_capacity, warehouse_used, game_over } = gameState;
  const capacityPercent = warehouse_capacity > 0 ? (warehouse_used / warehouse_capacity) * 100 : 0;

  const handleRefresh = async () => {
    setRefreshing(true);
    await onRefresh();
    setRefreshing(false);
  };

  const handleReset = async () => {
    setResetting(true);
    try {
      await request('POST', API_ENDPOINTS.game.reset);
      await onRefresh();
      setShowResetModal(false);
      window.location.reload();
    } catch (e) {
      // ignore
    } finally {
      setResetting(false);
    }
  };

  return (
    <>
      <header className="sticky top-0 z-40 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            {/* Left: Game Info */}
            <div className="flex items-center gap-8">
              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400">Day</p>
                <p className="text-3xl font-bold text-gray-900 dark:text-white">{current_day}</p>
              </div>

              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400">Wallet</p>
                <p className={`text-2xl font-bold ${wallet_balance < 0 ? 'text-red-600' : wallet_balance < 5000 ? 'text-yellow-600' : 'text-green-600'}`}>
                  {formatCurrency(wallet_balance)}
                </p>
              </div>

              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400">Warehouse {capacityPercent.toFixed(0)}%</p>
                <div className="w-32 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full transition-all ${capacityPercent > 80 ? 'bg-red-500' : capacityPercent > 60 ? 'bg-yellow-500' : 'bg-blue-500'}`}
                    style={{ width: `${Math.min(capacityPercent, 100)}%` }}
                  />
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {Math.round(warehouse_used).toLocaleString()} / {warehouse_capacity.toLocaleString()}
                </p>
              </div>

              {game_over && (
                <div className="bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-100 px-4 py-2 rounded-lg">
                  <p className="font-bold">Game Over</p>
                </div>
              )}
            </div>

            {/* Right: Actions */}
            <div className="flex items-center gap-2">
              <button
                onClick={handleRefresh}
                disabled={refreshing}
                className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition"
                title="Refresh game state"
              >
                <RefreshCw size={20} className={refreshing ? 'animate-spin text-blue-500' : ''} />
              </button>

              <button
                onClick={toggleTheme}
                className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition"
                title="Toggle dark/light mode"
              >
                {isDark ? <Sun size={20} /> : <Moon size={20} />}
              </button>

              <button
                onClick={() => setShowResetModal(true)}
                className="flex items-center gap-2 px-3 py-2 bg-red-100 hover:bg-red-200 dark:bg-red-900 dark:hover:bg-red-800 text-red-700 dark:text-red-300 rounded-lg text-sm font-medium transition"
                title="Start new game"
              >
                <RotateCcw size={16} />
                New Game
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Reset Confirmation Modal */}
      {showResetModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 p-6 rounded-lg max-w-sm w-full mx-4 shadow-xl">
            <h3 className="text-xl font-bold mb-2 text-red-600">Start New Game?</h3>
            <p className="text-gray-600 dark:text-gray-400 mb-6">
              This will reset everything — wallet, inventory, all orders, and event history. Day 1, €10,000.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowResetModal(false)}
                className="flex-1 px-4 py-2 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 rounded-lg transition"
              >
                Cancel
              </button>
              <button
                onClick={handleReset}
                disabled={resetting}
                className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-700 disabled:bg-gray-400 text-white rounded-lg font-medium transition"
              >
                {resetting ? 'Resetting...' : 'Reset & Start Over'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default GameHeader;
