import { useAPI } from '../../hooks/useAPI';
import { useLocalStorage } from '../../hooks/useLocalStorage';
import { useState, useEffect, useCallback } from 'react';
import { API_ENDPOINTS } from '../../utils/constants';
import { formatCurrency } from '../../utils/formatting';

const DEMAND_STATUS_BADGE = {
  open: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  fulfilled: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  partial: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  lost: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
};

// Modal shown when materials are missing
const ShortageModal = ({ order, shortages, onClose }) => (
  <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
    <div className="bg-white dark:bg-gray-800 p-6 rounded-lg max-w-md w-full mx-4 shadow-xl">
      <h3 className="text-lg font-bold mb-1 text-red-600">Insufficient Materials</h3>
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
        Cannot produce <strong>{order.quantity}× {order.product_name}</strong>. Missing:
      </p>
      <div className="space-y-2 mb-6">
        {shortages.map(s => (
          <div key={s.material_id} className="flex justify-between text-sm bg-red-50 dark:bg-red-950 rounded px-3 py-2">
            <span className="font-medium">{s.material_name}</span>
            <span className="text-red-600 font-medium">
              Need {s.total_required} · Have {s.available} · Short {s.shortage}
            </span>
          </div>
        ))}
      </div>
      <button
        onClick={onClose}
        className="w-full px-4 py-2 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 rounded-lg transition"
      >
        Close
      </button>
    </div>
  </div>
);

const GameTab = ({ gameState, onRefresh, onToast }) => {
  const { request, loading } = useAPI();
  const [showAdvanceModal, setShowAdvanceModal] = useState(false);
  const [demandOrders, setDemandOrders] = useState([]);
  const [activeOrders, setActiveOrders] = useState([]); // manufacturing orders in pending/released
  const [lastDayResult, setLastDayResult] = useState(null);
  const [producingId, setProducingId] = useState(null); // demand_id currently being API-processed
  const [servingId, setServingId] = useState(null); // demand_id currently being served
  const [shortageModal, setShortageModal] = useState(null); // { order, shortages }
  const [finishedGoods, setFinishedGoods] = useState({}); // { product_id: available_qty }
  const [products, setProducts] = useState([]); // finished product catalog
  const [demandMoMap, setDemandMoMap] = useLocalStorage('printer-sim-demand-mo-map', {}); // { demand_id: mo_order_id }
  const [todayRevenue, setTodayRevenue] = useState(0); // revenue collected this day

  const loadData = useCallback(async () => {
    try {
      const [demands, mos, goods, prods] = await Promise.all([
        request('GET', API_ENDPOINTS.game.demandOrders),
        request('GET', API_ENDPOINTS.manufacturing.list),
        request('GET', API_ENDPOINTS.game.finishedGoods),
        request('GET', API_ENDPOINTS.game.products),
      ]);
      setDemandOrders(demands);
      setActiveOrders(mos.filter(o => o.status === 'pending' || o.status === 'released'));
      setFinishedGoods(goods || {});
      setProducts(prods || []);
    } catch (e) {
      // silently fail
    }
  }, [request]);

  const loadDemandOrders = loadData;

  useEffect(() => {
    loadDemandOrders();
  }, [gameState?.current_day]);

  const handleAdvanceDay = async () => {
    try {
      const result = await request('POST', API_ENDPOINTS.game.advanceDay);
      await onRefresh();
      await loadDemandOrders();
      const dayResult = result?.data || result;
      setLastDayResult({ ...dayResult, revenue: todayRevenue });
      setTodayRevenue(0);
      setDemandMoMap({});
      setShowAdvanceModal(false);
      onToast(`Day advanced — ${result?.data?.demands_created ?? result?.demands_created ?? 0} new demand orders`, 'success');
    } catch (error) {
      onToast(error.message, 'error');
    }
  };

  const handleProduce = async (order) => {
    setProducingId(order.demand_id);
    try {
      const mo = await request('POST', API_ENDPOINTS.manufacturing.create, {
        product_id: order.product_id,
        quantity: order.quantity,
      });

      // Check BOM for shortages
      const shortages = mo.bom.filter(item => item.shortage > 0);

      if (shortages.length > 0) {
        await request('PUT', API_ENDPOINTS.manufacturing.cancel(mo.order_id));
        setShortageModal({ order, shortages });
      } else {
        await request('PUT', API_ENDPOINTS.manufacturing.release(mo.order_id), { quantity: order.quantity });
        setDemandMoMap(prev => ({ ...prev, [order.demand_id]: mo.order_id }));
        onToast(`Production started: ${order.quantity}× ${order.product_name}`, 'success');
        await loadData();
        onRefresh();
      }
    } catch (e) {
      onToast(e.message, 'error');
    } finally {
      setProducingId(null);
    }
  };

  const handleServe = async (order) => {
    setServingId(order.demand_id);
    try {
      const result = await request('POST', API_ENDPOINTS.game.fulfillDemand(order.demand_id));
      if (result.on_time) {
        setTodayRevenue(prev => prev + (result.revenue ?? 0));
        onToast(`Served ${result.qty_served}× ${order.product_name} — +${formatCurrency(result.revenue)}`, 'success');
      } else {
        onToast(`Served late — no revenue for ${order.product_name}`, 'error');
      }
      await loadData();
      onRefresh();
    } catch (e) {
      onToast(e.message, 'error');
    } finally {
      setServingId(null);
    }
  };

  const openOrders = demandOrders.filter(d => d.status === 'open' || d.status === 'partial');
  const closedOrders = demandOrders.filter(d => d.status !== 'open' && d.status !== 'partial');

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-600 dark:text-gray-400">Open Demand</p>
          <p className="text-3xl font-bold text-yellow-600">{openOrders.length}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-600 dark:text-gray-400">Total Demand</p>
          <p className="text-3xl font-bold text-blue-600">{demandOrders.length}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-600 dark:text-gray-400">Fulfilled</p>
          <p className="text-3xl font-bold text-green-600">
            {demandOrders.filter(d => d.status === 'fulfilled').length}
          </p>
        </div>
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-600 dark:text-gray-400">Lost</p>
          <p className="text-3xl font-bold text-red-600">
            {demandOrders.filter(d => d.status === 'lost').length}
          </p>
        </div>
      </div>

      {/* Last Day Summary */}
      {lastDayResult && (
        <div className="bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
          <p className="font-semibold text-blue-800 dark:text-blue-200 mb-2">
            Day {lastDayResult.day} Summary
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            <div>
              <p className="text-blue-600 dark:text-blue-400">New orders</p>
              <p className="font-bold">{lastDayResult.demands_created}</p>
            </div>
            <div>
              <p className="text-blue-600 dark:text-blue-400">Produced</p>
              <p className="font-bold">{lastDayResult.produced} units</p>
            </div>
            <div>
              <p className="text-blue-600 dark:text-blue-400">Revenue</p>
              <p className="font-bold text-green-600">{formatCurrency(lastDayResult.revenue)}</p>
            </div>
            <div>
              <p className="text-blue-600 dark:text-blue-400">Costs</p>
              <p className="font-bold text-red-600">{formatCurrency(lastDayResult.production_cost)}</p>
            </div>
          </div>
        </div>
      )}

      {/* Finished Goods Stock */}
      {products.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <p className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Finished Goods Stock</p>
          <div className="grid grid-cols-3 gap-3">
            {products.map(p => {
              const qty = finishedGoods[String(p.product_id)] ?? finishedGoods[p.product_id] ?? 0;
              return (
                <div key={p.product_id} className="text-center">
                  <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{p.product_name}</p>
                  <p className={`text-2xl font-bold ${qty > 0 ? 'text-green-600' : 'text-gray-400'}`}>{qty}</p>
                  <p className="text-xs text-gray-400">units</p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Advance Day Button */}
      <button
        onClick={() => setShowAdvanceModal(true)}
        disabled={gameState?.game_over || loading}
        className="w-full px-6 py-4 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-bold text-lg rounded-lg transition"
      >
        {loading ? 'Processing...' : `⏭ Advance to Day ${(gameState?.current_day ?? 1) + 1}`}
      </button>

      {/* Open Demand Orders */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center">
          <h3 className="font-bold">Open Demand Orders</h3>
          <button
            onClick={loadDemandOrders}
            className="text-sm text-blue-600 hover:text-blue-700 transition"
          >
            Refresh
          </button>
        </div>

        {openOrders.length === 0 ? (
          <div className="p-8 text-center text-gray-500 dark:text-gray-400">
            No open demand orders. Advance the day to generate new orders.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-700">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-600 dark:text-gray-400">Product</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600 dark:text-gray-400">Qty</th>
                <th className="px-4 py-3 text-center font-medium text-gray-600 dark:text-gray-400">Requested</th>
                <th className="px-4 py-3 text-center font-medium text-gray-600 dark:text-gray-400">Due</th>
                <th className="px-4 py-3 text-center font-medium text-gray-600 dark:text-gray-400">Status</th>
                <th className="px-4 py-3 text-center font-medium text-gray-600 dark:text-gray-400">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
              {openOrders.map(order => {
                const currentDay = gameState?.current_day ?? 1;
                const daysLeft = order.due_day - currentDay;
                const urgent = daysLeft <= 1;
                const isProcessing = producingId === order.demand_id;
                const isServing = servingId === order.demand_id;
                const linkedMoId = demandMoMap[order.demand_id];
                const inProduction = linkedMoId != null && activeOrders.some(mo => mo.order_id === linkedMoId);
                const availableStock = finishedGoods[String(order.product_id)] ?? finishedGoods[order.product_id] ?? 0;
                const remaining = order.quantity - (order.fulfilled_qty ?? 0);
                const isLate = currentDay > order.due_day;
                const canServe = availableStock > 0 && !isLate;
                const isFull = availableStock >= remaining;
                const isPartial = canServe && !isFull;
                return (
                  <tr
                    key={order.demand_id}
                    className={`hover:bg-gray-50 dark:hover:bg-gray-700 ${urgent ? 'bg-red-50 dark:bg-red-950' : ''}`}
                  >
                    <td className="px-4 py-3 font-medium">
                      {order.product_name}
                      {urgent && !isLate && <span className="ml-2 text-xs text-red-500 font-normal">⚠ Urgent</span>}
                      {isLate && <span className="ml-2 text-xs text-red-600 font-semibold">EXPIRED</span>}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {order.fulfilled_qty > 0
                        ? <span>{order.fulfilled_qty}<span className="text-gray-400">/{order.quantity}</span></span>
                        : order.quantity}
                    </td>
                    <td className="px-4 py-3 text-center text-gray-500">Day {order.request_day}</td>
                    <td className={`px-4 py-3 text-center font-medium ${urgent ? 'text-red-500' : 'text-gray-700 dark:text-gray-300'}`}>
                      Day {order.due_day}
                      <span className="ml-1 text-xs text-gray-400">({daysLeft}d)</span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${DEMAND_STATUS_BADGE[order.status] || ''}`}>
                        {order.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      {isLate ? (
                        <span className="px-3 py-1 text-xs font-medium bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400 rounded-lg">
                          Expired
                        </span>
                      ) : canServe ? (
                        <button
                          onClick={() => handleServe(order)}
                          disabled={isServing || loading}
                          className={`px-3 py-1 text-xs font-medium text-white rounded-lg transition disabled:bg-gray-400 ${isFull ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-amber-500 hover:bg-amber-600'}`}
                          title={isFull ? 'Serve full order' : `Partial: ${availableStock} of ${remaining} available`}
                        >
                          {isServing ? '⏳' : isFull ? '✓ Serve' : `◑ Partial (${availableStock}/${remaining})`}
                        </button>
                      ) : inProduction ? (
                        <span className="inline-flex items-center gap-1 px-3 py-1 text-xs font-medium bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300 rounded-lg">
                          <span className="w-1.5 h-1.5 rounded-full bg-purple-500 animate-pulse" />
                          In Production
                        </span>
                      ) : (
                        <button
                          onClick={() => handleProduce(order)}
                          disabled={isProcessing || loading}
                          className="px-3 py-1 text-xs font-medium bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white rounded-lg transition"
                          title={`Produce ${remaining} units`}
                        >
                          {isProcessing ? '⏳' : '▶ Produce'}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Closed Demand Orders (collapsible) */}
      {closedOrders.length > 0 && (
        <details className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
          <summary className="p-4 cursor-pointer font-medium text-gray-600 dark:text-gray-400 select-none">
            History ({closedOrders.length} orders)
          </summary>
          <div className="border-t border-gray-200 dark:border-gray-700">
            {closedOrders.map(order => (
              <div
                key={order.demand_id}
                className="px-4 py-3 flex justify-between text-sm border-b border-gray-100 dark:border-gray-700 last:border-0"
              >
                <span>{order.product_name} × {order.quantity} (Day {order.due_day})</span>
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${DEMAND_STATUS_BADGE[order.status] || ''}`}>
                  {order.status}
                </span>
              </div>
            ))}
          </div>
        </details>
      )}

      {/* Advance Day Modal */}
      {showAdvanceModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 p-6 rounded-lg max-w-md w-full mx-4 shadow-xl">
            <h3 className="text-xl font-bold mb-2">Advance to Day {(gameState?.current_day ?? 1) + 1}?</h3>
            <p className="text-gray-600 dark:text-gray-400 mb-6">
              This will process production, purchase deliveries, generate new demand, fulfill orders, and deduct daily costs.
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

      {/* Shortage Modal */}
      {shortageModal && (
        <ShortageModal
          order={shortageModal.order}
          shortages={shortageModal.shortages}
          onClose={() => setShortageModal(null)}
        />
      )}
    </div>
  );
};

export default GameTab;
