/**
 * useGameState - Custom hook for global game state
 */

import { useState, useEffect, useCallback } from 'react';
import useAPI from './useAPI';
import { API_ENDPOINTS } from '../utils/constants';

export const useGameState = () => {
  const { request } = useAPI();
  const [gameState, setGameState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchGameState = useCallback(async () => {
    try {
      const response = await request('GET', API_ENDPOINTS.game.state);
      setGameState(response);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [request]);

  useEffect(() => {
    fetchGameState();
  }, [fetchGameState]);

  const refreshGameState = useCallback(() => {
    return fetchGameState();
  }, [fetchGameState]);

  return {
    gameState,
    loading,
    error,
    refresh: refreshGameState,
  };
};

export default useGameState;
