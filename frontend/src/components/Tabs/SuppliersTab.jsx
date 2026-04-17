import { useEffect, useState } from 'react';
import { useAPI } from '../../hooks/useAPI';
import { API_ENDPOINTS } from '../../utils/constants';
import { formatCurrency } from '../../utils/formatting';

const PO_STATUS_BADGE = {
  pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  delivered: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  delayed: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
  cancelled: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300',
};

const SuppliersTab = ({ gameState, onRefresh, onToast }) => {
  const { request, loading } = useAPI();
  const [suppliers, setSuppliers] = useState([]);
  const [selectedSupplierId, setSelectedSupplierId] = useState(null);
  const [catalog, setCatalog] = useState(null);
  const [purchaseOrders, setPurchaseOrders] = useState([]);
  const [showOrderForm, setShowOrderForm] = useState(false);
  const [orderForm, setOrderForm] = useState({ material_id: '', quantity: 1 });

  const loadSuppliers = async () => {
    try {
      const data = await request('GET', API_ENDPOINTS.purchasing.suppliers);
      setSuppliers(data);
    } catch (e) {
      onToast(e.message, 'error');
    }
  };

  const loadPurchaseOrders = async () => {
    try {
      const data = await request('GET', API_ENDPOINTS.purchasing.orders);
      setPurchaseOrders(data);
    } catch (e) {
      onToast(e.message, 'error');
    }
  };

  const loadCatalog = async (supplierId) => {
    try {
      const data = await request('GET', API_ENDPOINTS.purchasing.catalog(supplierId));
      setCatalog(data);
      setSelectedSupplierId(supplierId);
      setOrderForm({ material_id: '', quantity: 1 });
      setShowOrderForm(false);
    } catch (e) {
      onToast(e.message, 'error');
    }
  };

  useEffect(() => {
    loadSuppliers();
    loadPurchaseOrders();
  }, []);

  const handleOrder = async () => {
    try {
      await request('POST', API_ENDPOINTS.purchasing.create, {
        supplier_id: selectedSupplierId,
        material_id: parseInt(orderForm.material_id),
        quantity: parseInt(orderForm.quantity),
      });
      onToast('Purchase order issued successfully', 'success');
      setShowOrderForm(false);
      setOrderForm({ material_id: '', quantity: 1 });
      await loadPurchaseOrders();
      onRefresh();
    } catch (e) {
      onToast(e.message, 'error');
    }
  };

  const selectedMaterial = catalog?.catalog.find(
    i => i.material_id === parseInt(orderForm.material_id)
  );
  const orderTotal = selectedMaterial
    ? selectedMaterial.current_price * parseInt(orderForm.quantity || 0)
    : 0;

  const pendingOrders = purchaseOrders.filter(o => o.status === 'pending');
  const totalSpent = purchaseOrders.reduce((s, o) => s + o.total_cost, 0);

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-600 dark:text-gray-400">Suppliers</p>
          <p className="text-3xl font-bold text-blue-600">{suppliers.length}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-600 dark:text-gray-400">Pending Deliveries</p>
          <p className="text-3xl font-bold text-yellow-600">{pendingOrders.length}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-600 dark:text-gray-400">Total Spent</p>
          <p className="text-2xl font-bold text-red-600">{formatCurrency(totalSpent)}</p>
        </div>
      </div>

      {/* Supplier Catalog Panel */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Supplier List */}
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
          <div className="p-4 border-b border-gray-200 dark:border-gray-700">
            <h3 className="font-bold">Suppliers</h3>
          </div>
          <div className="divide-y divide-gray-100 dark:divide-gray-700">
            {suppliers.map(supplier => (
              <button
                key={supplier.supplier_id}
                onClick={() => loadCatalog(supplier.supplier_id)}
                className={`w-full px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-gray-700 transition ${
                  selectedSupplierId === supplier.supplier_id
                    ? 'bg-blue-50 dark:bg-blue-950 border-l-4 border-blue-500'
                    : ''
                }`}
              >
                <p className="font-medium">{supplier.supplier_name}</p>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Lead time: {supplier.lead_time_days}d · Reliability: {(supplier.reliability * 100).toFixed(0)}%
                </p>
              </button>
            ))}
          </div>
        </div>

        {/* Catalog + Order Form */}
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
          <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center">
            <h3 className="font-bold">
              {catalog ? `${catalog.supplier_name} — Catalog` : 'Select a supplier'}
            </h3>
            {catalog && (
              <button
                onClick={() => setShowOrderForm(!showOrderForm)}
                className="px-3 py-1 text-sm bg-green-600 hover:bg-green-700 text-white rounded-lg transition"
              >
                + Order
              </button>
            )}
          </div>

          {!catalog && (
            <div className="p-10 text-center text-gray-500 dark:text-gray-400">
              Click a supplier on the left to view pricing
            </div>
          )}

          {catalog && (
            <>
              {/* Inline Order Form */}
              {showOrderForm && (
                <div className="p-4 bg-gray-50 dark:bg-gray-700 border-b border-gray-200 dark:border-gray-600">
                  <div className="flex gap-2 mb-2">
                    <select
                      value={orderForm.material_id}
                      onChange={e => setOrderForm(f => ({ ...f, material_id: e.target.value }))}
                      className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-sm"
                    >
                      <option value="">Select material...</option>
                      {catalog.catalog.map(item => (
                        <option key={item.material_id} value={item.material_id}>
                          {item.material_name} — {formatCurrency(item.current_price)}/u
                        </option>
                      ))}
                    </select>
                    <input
                      type="number"
                      min="1"
                      value={orderForm.quantity}
                      onChange={e => setOrderForm(f => ({ ...f, quantity: e.target.value }))}
                      className="w-20 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-sm"
                    />
                    <button
                      onClick={handleOrder}
                      disabled={!orderForm.material_id || loading}
                      className="px-3 py-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white rounded-lg text-sm transition"
                    >
                      {loading ? '...' : 'Buy'}
                    </button>
                  </div>
                  {selectedMaterial && (
                    <p className="text-xs text-gray-600 dark:text-gray-400">
                      Total: <strong>{formatCurrency(orderTotal)}</strong> · Delivery day:{' '}
                      {(gameState?.current_day || 1) + catalog.lead_time_days}
                    </p>
                  )}
                </div>
              )}

              {/* Catalog Items */}
              <div className="divide-y divide-gray-100 dark:divide-gray-700">
                {catalog.catalog.map(item => (
                  <div key={item.material_id} className="px-4 py-3 flex justify-between text-sm">
                    <span className="font-medium">{item.material_name}</span>
                    <div className="text-right">
                      <p className="font-semibold text-green-600">{formatCurrency(item.current_price)}/unit</p>
                      <p className="text-xs text-gray-500">Base: {formatCurrency(item.base_unit_cost)}</p>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Purchase Orders Table */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center">
          <h3 className="font-bold">Purchase Orders</h3>
          <button
            onClick={loadPurchaseOrders}
            disabled={loading}
            className="text-sm text-blue-600 hover:text-blue-700 disabled:text-gray-400 transition"
          >
            Refresh
          </button>
        </div>
        {purchaseOrders.length === 0 ? (
          <div className="p-8 text-center text-gray-500 dark:text-gray-400">
            No purchase orders yet. Select a supplier and place an order.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-700">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-gray-600 dark:text-gray-400">PO #</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600 dark:text-gray-400">Material</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600 dark:text-gray-400">Supplier</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-600 dark:text-gray-400">Qty</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-600 dark:text-gray-400">Total</th>
                  <th className="px-4 py-3 text-center font-medium text-gray-600 dark:text-gray-400">Delivery Day</th>
                  <th className="px-4 py-3 text-center font-medium text-gray-600 dark:text-gray-400">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {[...purchaseOrders].reverse().map(po => (
                  <tr key={po.po_id} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                    <td className="px-4 py-3 font-medium">#{po.po_id}</td>
                    <td className="px-4 py-3">{po.material_name}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{po.supplier_name}</td>
                    <td className="px-4 py-3 text-right">{po.quantity}</td>
                    <td className="px-4 py-3 text-right font-medium">{formatCurrency(po.total_cost)}</td>
                    <td className="px-4 py-3 text-center text-gray-600 dark:text-gray-400">
                      Day {po.expected_delivery_day}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${PO_STATUS_BADGE[po.status] || ''}`}>
                        {po.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default SuppliersTab;
