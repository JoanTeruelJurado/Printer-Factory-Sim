import { useState } from 'react';
import { Play } from 'lucide-react';
import SimDashboard from './Tabs/SimDashboard';
import GameTab from './Tabs/GameTab';
import OrdersTab from './Tabs/OrdersTab';
import InventoryTab from './Tabs/InventoryTab';
import SuppliersTab from './Tabs/SuppliersTab';
import EventsTab from './Tabs/EventsTab';

const GameTabs = ({ gameState, onRefresh, onToast }) => {
  const [activeTab, setActiveTab] = useState('simulation');

  const tabs = [
    { id: 'simulation', label: 'Simulation', icon: <Play size={16} /> },
    { id: 'game', label: 'Game', icon: '🎮' },
    { id: 'orders', label: 'Orders', icon: '📋' },
    { id: 'inventory', label: 'Inventory', icon: '📦' },
    { id: 'suppliers', label: 'Suppliers', icon: '🏭' },
    { id: 'events', label: 'Events', icon: '📋' },
  ];

  return (
    <div className="flex-1 flex flex-col">
      {/* Tab Navigation */}
      <div className="border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex gap-8 overflow-x-auto">
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`py-4 px-1 border-b-2 font-medium text-sm transition whitespace-nowrap ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                    : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-300'
                }`}
              >
                <span className="mr-2 inline-flex items-center">{tab.icon}</span>
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-y-auto bg-gray-50 dark:bg-gray-900">
        <div className="max-w-7xl mx-auto px-4 py-6">
          {activeTab === 'simulation' && <SimDashboard gameState={gameState} onRefresh={onRefresh} onToast={onToast} />}
          {activeTab === 'game' && <GameTab gameState={gameState} onRefresh={onRefresh} onToast={onToast} />}
          {activeTab === 'orders' && <OrdersTab gameState={gameState} onRefresh={onRefresh} onToast={onToast} />}
          {activeTab === 'inventory' && <InventoryTab gameState={gameState} onRefresh={onRefresh} onToast={onToast} />}
          {activeTab === 'suppliers' && <SuppliersTab gameState={gameState} onRefresh={onRefresh} onToast={onToast} />}
          {activeTab === 'events' && <EventsTab gameState={gameState} onRefresh={onRefresh} onToast={onToast} />}
        </div>
      </div>
    </div>
  );
};

export default GameTabs;
