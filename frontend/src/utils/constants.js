/**
 * Application constants
 */

export const COLORS = {
  dark: {
    bg: '#0f1419',
    surface: '#1a1f26',
    text: '#e0e0e0',
    textSecondary: '#a0a0a0',
    border: '#2d3139',
  },
  light: {
    bg: '#ffffff',
    surface: '#f5f5f5',
    text: '#1a1a1a',
    textSecondary: '#666666',
    border: '#e0e0e0',
  },
  status: {
    success: '#10b981',
    warning: '#f59e0b',
    error: '#ef4444',
    info: '#3b82f6',
    pending: '#f59e0b',
    released: '#3b82f6',
    production: '#8b5cf6',
    completed: '#10b981',
  }
};

export const BREAKPOINTS = {
  mobile: 600,
  tablet: 1024,
  desktop: 1280,
};

export const ORDER_STATUSES = [
  { value: 'pending', label: 'Pending', color: 'warning' },
  { value: 'released', label: 'Released', color: 'info' },
  { value: 'in-production', label: 'In Production', color: 'production' },
  { value: 'completed', label: 'Completed', color: 'success' },
];

export const EVENT_TYPES = [
  'all',
  'demand',
  'production',
  'purchase',
  'fulfillment',
  'cost',
  'game_over',
];

export const API_ENDPOINTS = {
  game: {
    state: '/game/state',
    advanceDay: '/game/advance-day',
    reset: '/game/reset',
    inventory: '/game/inventory',
    products: '/game/products',
    events: '/game/events',
    demandOrders: '/game/demand-orders',
    finishedGoods: '/game/finished-goods',
    fulfillDemand: (id) => `/game/demand-orders/${id}/fulfill`,
  },
  manufacturing: {
    list: '/manufacturing-orders',
    create: '/manufacturing-orders',
    get: (id) => `/manufacturing-orders/${id}`,
    release: (id) => `/manufacturing-orders/${id}/release`,
    cancel: (id) => `/manufacturing-orders/${id}/cancel`,
  },
  purchasing: {
    suppliers: '/suppliers',
    catalog: (id) => `/suppliers/${id}/catalog`,
    pricing: (supplierId, materialId) => `/suppliers/${supplierId}/pricing/${materialId}`,
    orders: '/purchase-orders',
    create: '/purchase-orders',
  },
  events: {
    list: '/events',
  },
  save: {
    export: '/game/export',
    import: '/game/import',
  },
};

export const TOAST_DURATION = 3000; // ms

export default {
  COLORS,
  BREAKPOINTS,
  ORDER_STATUSES,
  EVENT_TYPES,
  API_ENDPOINTS,
  TOAST_DURATION,
};
