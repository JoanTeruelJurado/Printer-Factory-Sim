/**
 * useAPI - Custom hook for API communication
 */

import { useState, useCallback } from 'react';
import API from '../utils/api';

export const useAPI = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const request = useCallback(async (method, endpoint, data = null) => {
    setLoading(true);
    setError(null);
    try {
      let response;
      if (method === 'GET') {
        response = await API.get(endpoint);
      } else if (method === 'POST') {
        response = await API.post(endpoint, data);
      } else if (method === 'PUT') {
        response = await API.put(endpoint, data);
      } else if (method === 'DELETE') {
        response = await API.delete(endpoint);
      }
      return response;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { request, loading, error };
};

export default useAPI;
