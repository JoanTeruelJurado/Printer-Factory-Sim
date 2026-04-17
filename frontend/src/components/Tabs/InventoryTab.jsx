import { useEffect, useState } from 'react';
import { useAPI } from '../../hooks/useAPI';
import { API_ENDPOINTS } from '../../utils/constants';

const InventoryTab = ({ gameState, onRefresh, onToast }) => {
  const { request, loading } = useAPI();
  const [inventory, setInventory] = useState([]);

  const loadInventory = async () => {
    try {
      const data = await request('GET', API_ENDPOINTS.game.inventory);
      setInventory(data);
    } catch (e) {
      onToast(e.message, 'error');
    }
  };

  useEffect(() => {
    loadInventory();
  }, [gameState?.current_day]);

  const warehouseUsed = gameState?.warehouse_used || 0;
  const warehouseCapacity = gameState?.warehouse_capacity || 10000;
  const capacityPct = Math.min(100, (warehouseUsed / warehouseCapacity) * 100);
  const capacityColor =
    capacityPct > 80 ? 'bg-red-500' : capacityPct > 60 ? 'bg-yellow-500' : 'bg-green-500';

  const totalStock = inventory.reduce((s, i) => s + i.quantity, 0);
  const totalReserved = inventory.reduce((s, i) => s + i.reserved_quantity, 0);
  const lowStockItems = inventory.filter(i => (i.quantity - i.reserved_quantity) < 20);

  return (
    <div className="space-y-6">
      {/* Warehouse Capacity Bar */}
      <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
        <div className="flex justify-between mb-2">
          <span className="font-semibold">Warehouse Capacity</span>
          <span className="text-sm text-gray-600 dark:text-gray-400">
            {Math.round(warehouseUsed).toLocaleString()} / {warehouseCapacity.toLocaleString()} units
          </span>
        </div>
        <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3">
          <div
            className={`h-3 rounded-full transition-all ${capacityColor}`}
            style={{ width: `${capacityPct}%` }}
          />
        </div>
        <p className="text-sm mt-1 text-gray-500 dark:text-gray-400">{capacityPct.toFixed(1)}% used</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-600 dark:text-gray-400">Material Types</p>
          <p className="text-3xl font-bold text-blue-600">{inventory.length}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-600 dark:text-gray-400">Total Stock</p>
          <p className="text-3xl font-bold text-green-600">{totalStock.toLocaleString()}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-600 dark:text-gray-400">Reserved</p>
          <p className="text-3xl font-bold text-yellow-600">{totalReserved.toLocaleString()}</p>
        </div>
      </div>

      {/* Low Stock Alert */}
      {lowStockItems.length > 0 && (
        <div className="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-4">
          <p className="font-medium text-red-700 dark:text-red-300 mb-1">
            ⚠ Low Stock Warning ({lowStockItems.length} materials)
          </p>
          <p className="text-sm text-red-600 dark:text-red-400">
            {lowStockItems.map(i => i.material_name).join(', ')}
          </p>
        </div>
      )}

      {/* Inventory Table */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center">
          <h3 className="font-bold">Material Stock Levels</h3>
          <button
            onClick={loadInventory}
            disabled={loading}
            className="text-sm text-blue-600 hover:text-blue-700 disabled:text-gray-400 transition"
          >
            {loading ? 'Loading...' : 'Refresh'}
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-700">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-600 dark:text-gray-400">Material</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600 dark:text-gray-400">In Stock</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600 dark:text-gray-400">Reserved</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600 dark:text-gray-400">Available</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600 dark:text-gray-400">Volume Used</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
              {inventory.map(item => {
                const available = item.quantity - item.reserved_quantity;
                const isLow = available < 20;
                return (
                  <tr
                    key={item.material_id}
                    className={`hover:bg-gray-50 dark:hover:bg-gray-700 ${isLow ? 'bg-red-50 dark:bg-red-950' : ''}`}
                  >
                    <td className="px-4 py-3 font-medium">
                      {item.material_name}
                      {isLow && (
                        <span className="ml-2 text-xs text-red-500 font-normal">⚠ Low</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">{item.quantity.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right text-yellow-600">{item.reserved_quantity.toLocaleString()}</td>
                    <td className={`px-4 py-3 text-right font-semibold ${available <= 0 ? 'text-red-500' : 'text-green-600'}`}>
                      {available.toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-right text-gray-500">{item.total_volume.toLocaleString()}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default InventoryTab;
