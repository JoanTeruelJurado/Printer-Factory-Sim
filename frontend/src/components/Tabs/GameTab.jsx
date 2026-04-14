import { useAPI } from '../../hooks/useAPI';
import { useState } from 'react';
import { API_ENDPOINTS } from '../../utils/constants';

const GameTab = ({ gameState, onRefresh, onToast }) => {
  const { request, loading } = useAPI();
  const [showAdvanceModal, setShowAdvanceModal] = useState(false);

  const handleAdvanceDay = async () => {
    try {
      await request('POST', API_ENDPOINTS.game.advanceDay);
      await onRefresh();
      setShowAdvanceModal(false);
      onToast('Day advanced successfully', 'success');
    } catch (error) {
      onToast(error.message, 'error');
    }
  };

  const demandOrders = gameState.demand_orders || [];
  const manufacturingOrders = gameState.manufacturing_orders || [];
  const pendingDemand = demandOrders.filter(d => d.status === 'pending').length;
  const producingOrders = manufacturingOrders.filter(m => m.status === 'in-production').length;

  return (
    <div className="space-y-6">
      {/* Game Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-600 dark:text-gray-400">Pending Demand</p>
          <p className="text-3xl font-bold text-blue-600">{pendingDemand}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-600 dark:text-gray-400">Producing Orders</p>
          <p className="text-3xl font-bold text-purple-600">{producingOrders}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-600 dark:text-gray-400">Total Materials</p>
          <p className="text-3xl font-bold text-green-600">
            {(gameState.inventory || []).reduce((sum, item) => sum + item.quantity, 0)}
          </p>
        </div>
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-600 dark:text-gray-400">Active Days</p>
          <p className="text-3xl font-bold text-gray-600">{gameState.day}</p>
        </div>
      </div>

      {/* Recent Events */}
      <div className="bg-white dark:bg-gray-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700">
        <h3 className="text-lg font-bold mb-4">Recent Events</h3>
        <div className="space-y-2 max-h-40 overflow-y-auto">
          {(gameState.events || []).slice(0, 5).map((event, idx) => (
            <div key={idx} className="text-sm text-gray-600 dark:text-gray-400 border-l-2 border-blue-500 pl-3 py-1">
              <p className="font-medium text-gray-900 dark:text-gray-100">{event.event_type || 'Unknown'}</p>
              <p className="text-xs">{event.description || 'No description'}</p>
            </div>
          ))}
          {(!gameState.events || gameState.events.length === 0) && (
            <p className="text-gray-500 dark:text-gray-400">No events yet</p>
          )}
        </div>
      </div>

      {/* Advance Day Button */}
      <div className="flex gap-4">
        <button
          onClick={() => setShowAdvanceModal(true)}
          disabled={gameState.game_over || loading}
          className="flex-1 px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-bold rounded-lg transition"
        >
          {loading ? 'Processing...' : '⏭️ Advance Day'}
        </button>
      </div>

      {/* Advance Day Modal */}
      {showAdvanceModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 p-6 rounded-lg max-w-md w-full mx-4">
            <h3 className="text-xl font-bold mb-4">Advance to Day {gameState.day + 1}?</h3>
            <p className="text-gray-600 dark:text-gray-400 mb-6">
              This will process production, deliveries, demand fulfillment, and costs for the day.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowAdvanceModal(false)}
                className="flex-1 px-4 py-2 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 rounded-lg transition"
              >
                Cancel
              </button>
              <button
                onClick={handleAdvanceDay}
                disabled={loading}
                className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white rounded-lg transition"
              >
                {loading ? 'Processing...' : 'Advance'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default GameTab;
