import { RefreshCw, Settings, HelpCircle, Moon, Sun } from 'lucide-react';
import { useTheme } from '../theme.jsx';
import { formatCurrency } from '../utils/formatting';

const GameHeader = ({ gameState, onRefresh }) => {
  const { isDark, toggleTheme } = useTheme();

  if (!gameState) return null;

  const { day, wallet, warehouse_capacity, daily_production_capacity, game_over } = gameState;
  const currentInventory = gameState.inventory ? gameState.inventory.reduce((sum, item) => sum + item.quantity, 0) : 0;
  const capacityPercent = (currentInventory / warehouse_capacity) * 100;

  return (
    <header className="sticky top-0 z-40 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 py-4">
        <div className="flex items-center justify-between">
          {/* Left: Game Info */}
          <div className="flex items-center gap-8">
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Day</p>
              <p className="text-3xl font-bold text-gray-900 dark:text-white">{day}</p>
            </div>

            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Wallet</p>
              <p className={`text-2xl font-bold ${wallet < 0 ? 'text-red-600' : wallet < 5000 ? 'text-yellow-600' : 'text-green-600'}`}>
                {formatCurrency(wallet)}
              </p>
            </div>

            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Warehouse {capacityPercent.toFixed(0)}%</p>
              <div className="w-32 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 transition-all"
                  style={{ width: `${Math.min(capacityPercent, 100)}%` }}
                ></div>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                {currentInventory} / {warehouse_capacity}
              </p>
            </div>

            {game_over && (
              <div className="bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-100 px-4 py-2 rounded">
                <p className="font-bold">Game Over</p>
              </div>
            )}
          </div>

          {/* Right: Actions */}
          <div className="flex items-center gap-2">
            <button
              onClick={onRefresh}
              className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition"
              title="Refresh game state"
            >
              <RefreshCw size={20} />
            </button>

            <button
              onClick={toggleTheme}
              className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition"
              title="Toggle dark/light mode"
            >
              {isDark ? <Sun size={20} /> : <Moon size={20} />}
            </button>

            <button
              className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition"
              title="Settings"
            >
              <Settings size={20} />
            </button>

            <button
              className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition"
              title="Help"
            >
              <HelpCircle size={20} />
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};

export default GameHeader;
