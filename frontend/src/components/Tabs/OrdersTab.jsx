import { useEffect, useState } from 'react';
import { useAPI } from '../../hooks/useAPI';
import { API_ENDPOINTS } from '../../utils/constants';

const STATUS_BADGE = {
  pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  released: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  completed: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  cancelled: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300',
};

const ReleaseModal = ({ order, onRelease, onClose, loading }) => {
  const [qty, setQty] = useState(order.remaining_qty);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 p-6 rounded-lg max-w-md w-full mx-4 shadow-xl">
        <h3 className="text-xl font-bold mb-1">Release Order #{order.order_id}</h3>
        <p className="text-gray-500 dark:text-gray-400 mb-4">{order.product_name}</p>
        <label className="block text-sm font-medium mb-1">
          Quantity to release (max {order.remaining_qty})
        </label>
        <input
          type="number"
          min="1"
          max={order.remaining_qty}
          value={qty}
          onChange={e => setQty(parseInt(e.target.value) || 1)}
          className="w-full px-3 py-2 mb-4 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700"
        />
        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 rounded-lg transition"
          >
            Cancel
          </button>
          <button
            onClick={() => onRelease(order.order_id, qty)}
            disabled={loading || qty < 1 || qty > order.remaining_qty}
            className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white rounded-lg transition"
          >
            {loading ? 'Releasing...' : 'Release to Production'}
          </button>
        </div>
      </div>
    </div>
  );
};

const OrdersTab = ({ gameState, onRefresh, onToast }) => {
  const { request, loading } = useAPI();
  const [orders, setOrders] = useState([]);
  const [products, setProducts] = useState([]);
  const [expandedOrder, setExpandedOrder] = useState(null);
  const [releaseModal, setReleaseModal] = useState(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createForm, setCreateForm] = useState({ product_id: '', quantity: 1 });

  const loadOrders = async () => {
    try {
      const data = await request('GET', API_ENDPOINTS.manufacturing.list);
      setOrders(data);
    } catch (e) {
      onToast(e.message, 'error');
    }
  };

  const loadProducts = async () => {
    try {
      const data = await request('GET', API_ENDPOINTS.game.products);
      setProducts(data);
    } catch (e) {
      // silently fail — products list is optional for display
    }
  };

  useEffect(() => {
    loadOrders();
    loadProducts();
  }, [gameState?.current_day]);

  const handleCreate = async () => {
    try {
      await request('POST', API_ENDPOINTS.manufacturing.create, {
        product_id: parseInt(createForm.product_id),
        quantity: parseInt(createForm.quantity),
      });
      onToast('Manufacturing order created', 'success');
      setShowCreateForm(false);
      setCreateForm({ product_id: '', quantity: 1 });
      await loadOrders();
    } catch (e) {
      onToast(e.message, 'error');
    }
  };

  const handleRelease = async (orderId, qty) => {
    try {
      await request('PUT', API_ENDPOINTS.manufacturing.release(orderId), { quantity: qty });
      onToast('Order released to production', 'success');
      setReleaseModal(null);
      await loadOrders();
      onRefresh();
    } catch (e) {
      onToast(e.message, 'error');
    }
  };

  const handleCancel = async (orderId) => {
    try {
      await request('PUT', API_ENDPOINTS.manufacturing.cancel(orderId));
      onToast('Order cancelled', 'success');
      await loadOrders();
    } catch (e) {
      onToast(e.message, 'error');
    }
  };

  const activeOrders = orders.filter(o => o.status !== 'cancelled' && o.status !== 'completed');
  const doneOrders = orders.filter(o => o.status === 'completed' || o.status === 'cancelled');

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-600 dark:text-gray-400">Active Orders</p>
          <p className="text-3xl font-bold text-blue-600">{activeOrders.length}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-600 dark:text-gray-400">Pending Release</p>
          <p className="text-3xl font-bold text-yellow-600">
            {orders.filter(o => o.status === 'pending').length}
          </p>
        </div>
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-600 dark:text-gray-400">In Production</p>
          <p className="text-3xl font-bold text-purple-600">
            {orders.filter(o => o.status === 'released').length}
          </p>
        </div>
      </div>

      {/* Header + Create Button */}
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-bold">Manufacturing Orders</h3>
        <button
          onClick={() => setShowCreateForm(!showCreateForm)}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition"
        >
          + New Order
        </button>
      </div>

      {/* Create Form */}
      {showCreateForm && (
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
          <h4 className="font-medium mb-3">Create Manufacturing Order</h4>
          <div className="flex gap-3">
            <select
              value={createForm.product_id}
              onChange={e => setCreateForm(f => ({ ...f, product_id: e.target.value }))}
              className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-sm"
            >
              <option value="">Select product...</option>
              {products.map(p => (
                <option key={p.product_id} value={p.product_id}>{p.product_name}</option>
              ))}
            </select>
            <input
              type="number"
              min="1"
              value={createForm.quantity}
              onChange={e => setCreateForm(f => ({ ...f, quantity: e.target.value }))}
              placeholder="Qty"
              className="w-24 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-sm"
            />
            <button
              onClick={handleCreate}
              disabled={!createForm.product_id || loading}
              className="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white rounded-lg text-sm font-medium transition"
            >
              Create
            </button>
            <button
              onClick={() => setShowCreateForm(false)}
              className="px-4 py-2 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 rounded-lg text-sm transition"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Active Orders List */}
      <div className="space-y-3">
        {activeOrders.length === 0 && (
          <div className="text-center py-10 text-gray-500 dark:text-gray-400 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
            No active manufacturing orders. Create one above.
          </div>
        )}
        {activeOrders.map(order => (
          <div
            key={order.order_id}
            className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700"
          >
            <div className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div>
                  <p className="font-medium">#{order.order_id} — {order.product_name}</p>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Qty: {order.quantity} · Remaining: {order.remaining_qty}
                  </p>
                </div>
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${STATUS_BADGE[order.status] || ''}`}>
                  {order.status}
                </span>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setExpandedOrder(expandedOrder === order.order_id ? null : order.order_id)}
                  className="px-3 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition"
                >
                  {expandedOrder === order.order_id ? 'Hide BOM' : 'View BOM'}
                </button>
                {order.status === 'pending' && (
                  <>
                    <button
                      onClick={() => setReleaseModal(order)}
                      className="px-3 py-1 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition"
                    >
                      Release
                    </button>
                    <button
                      onClick={() => handleCancel(order.order_id)}
                      disabled={loading}
                      className="px-3 py-1 text-sm bg-red-600 hover:bg-red-700 disabled:bg-gray-400 text-white rounded-lg transition"
                    >
                      Cancel
                    </button>
                  </>
                )}
              </div>
            </div>

            {/* BOM Breakdown */}
            {expandedOrder === order.order_id && order.bom.length > 0 && (
              <div className="border-t border-gray-200 dark:border-gray-700 p-4 bg-gray-50 dark:bg-gray-750">
                <p className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-2">Bill of Materials</p>
                <div className="space-y-2">
                  {order.bom.map(item => (
                    <div key={item.material_id} className="flex justify-between text-sm">
                      <span className="font-medium">{item.material_name}</span>
                      <div className="flex gap-6 text-right">
                        <span className="text-gray-500 dark:text-gray-400">
                          {item.qty_per_unit}/unit · Need: {item.total_required}
                        </span>
                        <span className={item.shortage > 0 ? 'text-red-500 font-medium' : 'text-green-600 font-medium'}>
                          {item.shortage > 0
                            ? `⚠ Short ${item.shortage}`
                            : `✓ OK (${item.available} avail)`}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* History */}
      {doneOrders.length > 0 && (
        <details className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
          <summary className="p-4 cursor-pointer font-medium text-gray-600 dark:text-gray-400 select-none">
            History ({doneOrders.length} orders)
          </summary>
          <div className="border-t border-gray-200 dark:border-gray-700">
            {doneOrders.map(order => (
              <div
                key={order.order_id}
                className="px-4 py-3 flex justify-between text-sm border-b border-gray-100 dark:border-gray-700 last:border-0"
              >
                <span>#{order.order_id} — {order.product_name} × {order.quantity}</span>
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_BADGE[order.status] || ''}`}>
                  {order.status}
                </span>
              </div>
            ))}
          </div>
        </details>
      )}

      {/* Release Modal */}
      {releaseModal && (
        <ReleaseModal
          order={releaseModal}
          onRelease={handleRelease}
          onClose={() => setReleaseModal(null)}
          loading={loading}
        />
      )}
    </div>
  );
};

export default OrdersTab;
