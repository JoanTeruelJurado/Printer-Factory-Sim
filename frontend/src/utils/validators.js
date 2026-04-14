/**
 * Form and input validators
 */

export const validatePositiveInteger = (value) => {
  const num = parseInt(value, 10);
  return !isNaN(num) && num > 0;
};

export const validateEmail = (email) => {
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return re.test(email);
};

export const validateRequired = (value) => {
  return value !== null && value !== undefined && value !== '';
};

export const validateRange = (value, min, max) => {
  const num = parseFloat(value);
  return !isNaN(num) && num >= min && num <= max;
};

export const validateOrderQuantity = (qty, maxCapacity) => {
  if (!validatePositiveInteger(qty)) return 'Quantity must be a positive integer';
  if (parseInt(qty, 10) > maxCapacity) return `Quantity exceeds capacity (max: ${maxCapacity})`;
  return null;
};

export const validatePurchaseQuantity = (qty, maxCapacity, currentInventory) => {
  if (!validatePositiveInteger(qty)) return 'Quantity must be a positive integer';
  if (currentInventory + parseInt(qty, 10) > maxCapacity) {
    return `Would exceed warehouse capacity (max: ${maxCapacity})`;
  }
  return null;
};

export default {
  validatePositiveInteger,
  validateEmail,
  validateRequired,
  validateRange,
  validateOrderQuantity,
  validatePurchaseQuantity,
};
