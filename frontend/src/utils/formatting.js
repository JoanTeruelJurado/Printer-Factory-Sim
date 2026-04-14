/**
 * Formatting utilities for currency, dates, and quantities
 */

export const formatCurrency = (amount) => {
  return new Intl.NumberFormat('es-ES', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 0,
  }).format(amount);
};

export const formatDate = (date) => {
  if (!date) return 'N/A';
  const d = new Date(date);
  return d.toLocaleDateString('es-ES', { month: 'short', day: 'numeric' });
};

export const formatQty = (qty, unit = 'units') => {
  return `${qty} ${unit}`;
};

export const getStatusColor = (status) => {
  const colors = {
    pending: 'yellow',
    released: 'blue',
    'in-production': 'purple',
    completed: 'green',
    success: 'green',
    warning: 'yellow',
    error: 'red',
    normal: 'blue',
  };
  return colors[status] || 'gray';
};

export const getStatusLabel = (status) => {
  const labels = {
    'pending': 'Pending',
    'released': 'Released',
    'in-production': 'In Production',
    'completed': 'Completed',
    'pending_delivery': 'Awaiting Delivery',
    'delivered': 'Delivered',
  };
  return labels[status] || status;
};

export default {
  formatCurrency,
  formatDate,
  formatQty,
  getStatusColor,
  getStatusLabel,
};
