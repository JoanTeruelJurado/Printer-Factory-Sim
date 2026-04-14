/**
 * API wrapper with fetch
 */

export const API = {
  async get(endpoint) {
    const response = await fetch(`/api${endpoint}`);
    if (!response.ok) throw new Error(`API error: ${response.statusText}`);
    return response.json();
  },

  async post(endpoint, data) {
    const response = await fetch(`/api${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.message || `API error: ${response.statusText}`);
    }
    return response.json();
  },

  async put(endpoint, data) {
    const response = await fetch(`/api${endpoint}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.message || `API error: ${response.statusText}`);
    }
    return response.json();
  },

  async delete(endpoint) {
    const response = await fetch(`/api${endpoint}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error(`API error: ${response.statusText}`);
    return response.json();
  },
};

export default API;
