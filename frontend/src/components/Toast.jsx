import { X, AlertCircle, CheckCircle, InfoIcon } from 'lucide-react';

const Toast = ({ toasts }) => {
  const getIcon = (type) => {
    switch (type) {
      case 'error':
        return <AlertCircle className="text-red-600" />;
      case 'success':
        return <CheckCircle className="text-green-600" />;
      default:
        return <InfoIcon className="text-blue-600" />;
    }
  };

  const getStyles = (type) => {
    const baseStyles = 'mb-3 p-4 rounded-lg flex items-start gap-3 shadow-lg animate-in fade-in slide-in-from-right';
    switch (type) {
      case 'error':
        return `${baseStyles} bg-red-50 dark:bg-red-900 text-red-800 dark:text-red-100`;
      case 'success':
        return `${baseStyles} bg-green-50 dark:bg-green-900 text-green-800 dark:text-green-100`;
      default:
        return `${baseStyles} bg-blue-50 dark:bg-blue-900 text-blue-800 dark:text-blue-100`;
    }
  };

  return (
    <div className="fixed bottom-4 right-4 max-w-md z-50">
      {toasts.map(toast => (
        <div key={toast.id} className={getStyles(toast.type)}>
          <div className="flex-shrink-0 mt-0.5">
            {getIcon(toast.type)}
          </div>
          <div className="flex-1">
            <p className="text-sm font-medium">{toast.message}</p>
          </div>
        </div>
      ))}
    </div>
  );
};

export default Toast;
