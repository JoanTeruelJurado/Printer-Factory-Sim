/**
 * useLocalStorage - Custom hook for localStorage persistence
 */

import { useState, useEffect } from 'react';

export const useLocalStorage = (key, defaultValue) => {
  const [value, setValue] = useState(() => {
    try {
      const item = window.localStorage.getItem(key);
      return item ? JSON.parse(item) : defaultValue;
    } catch {
      return defaultValue;
    }
  });

  const setStoredValue = (val) => {
    try {
      const valueToStore = val instanceof Function ? val(value) : val;
      setValue(valueToStore);
      window.localStorage.setItem(key, JSON.stringify(valueToStore));
    } catch (error) {
      console.error('localStorage error:', error);
    }
  };

  return [value, setStoredValue];
};

export default useLocalStorage;
