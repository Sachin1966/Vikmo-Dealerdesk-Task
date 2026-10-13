// API Client for VIKMO DealerDesk Backend

const API_BASE = '/api';

export async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const { headers: customHeaders, ...restOptions } = options;
  const config = {
    ...restOptions,
    headers: {
      'Content-Type': 'application/json',
      ...customHeaders,
    },
  };

  try {
    const response = await fetch(url, config);
    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      const errObj = data.error || {};
      const msg = errObj.message || data.message || `Request failed with status ${response.status}`;
      const code = errObj.code || data.error_code || 'UNKNOWN_ERROR';
      const details = errObj.details || data.details || null;
      const error = new Error(msg);
      error.status = response.status;
      error.code = code;
      error.details = details;
      throw error;
    }

    return data;
  } catch (err) {
    if (!err.status) {
      // Network or connection error (e.g. Django server down)
      const error = new Error(`Cannot connect to DealerDesk API at ${url}. Is Django running?`);
      error.status = 503;
      error.code = 'BACKEND_OFFLINE';
      throw error;
    }
    throw err;
  }
}

// Products
export function getProducts(params = {}) {
  const query = new URLSearchParams();
  if (params.search) query.set('search', params.search);
  if (params.category) query.set('category', params.category);
  if (params.vehicle_fitment) query.set('vehicle_fitment', params.vehicle_fitment);
  if (params.page) query.set('page', params.page);
  return request(`/products/?${query.toString()}`);
}

export function getProduct(sku) {
  return request(`/products/${encodeURIComponent(sku)}/`);
}

// Dealers
export function getDealers() {
  return request('/dealers/');
}

// Orders
export function getOrders(status = '') {
  const query = status ? `?status=${encodeURIComponent(status)}` : '';
  return request(`/orders/${query}`);
}

export function getOrder(orderNumber) {
  return request(`/orders/${encodeURIComponent(orderNumber)}/`);
}

export function createDraftOrder(dealerId, items, idempotencyKey) {
  const headers = {};
  if (idempotencyKey) {
    headers['Idempotency-Key'] = idempotencyKey;
  }
  return request('/orders/', {
    method: 'POST',
    headers,
    body: JSON.stringify({
      dealer_id: Number(dealerId),
      items: items.map(item => ({
        sku: item.sku,
        quantity: Number(item.quantity),
      })),
    }),
  });
}

export function confirmOrder(orderNumber) {
  return request(`/orders/${encodeURIComponent(orderNumber)}/confirm/`, {
    method: 'POST',
  });
}

export function dispatchOrder(orderNumber) {
  return request(`/orders/${encodeURIComponent(orderNumber)}/dispatch/`, {
    method: 'POST',
  });
}

export function deliverOrder(orderNumber) {
  return request(`/orders/${encodeURIComponent(orderNumber)}/deliver/`, {
    method: 'POST',
  });
}

export function cancelOrder(orderNumber) {
  return request(`/orders/${encodeURIComponent(orderNumber)}/cancel/`, {
    method: 'POST',
  });
}

// AI Assistant
export function chatWithAssistant(sessionId, dealerId, message) {
  return request('/assistant/chat/', {
    method: 'POST',
    body: JSON.stringify({
      session_id: sessionId,
      dealer_id: Number(dealerId),
      message,
    }),
  });
}

// Forecasting & Reorder Suggestions
export function getForecast(sku) {
  return request(`/forecast/${encodeURIComponent(sku)}/`);
}

export function getReorderSuggestions() {
  return request('/reorder-suggestions/');
}

// Supplier Sync
export function syncSupplier() {
  return request('/sync/supplier/', {
    method: 'POST',
  });
}
