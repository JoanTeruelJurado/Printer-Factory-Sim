import { useEffect, useState } from 'react';
import { useAPI } from '../../hooks/useAPI';
import { API_ENDPOINTS } from '../../utils/constants';

const CATEGORY_BADGE = {
  production: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
  purchase: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  demand: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  inventory: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  financial: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
  system: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300',
  alert: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
};

const CATEGORIES = ['all', 'production', 'purchase', 'demand', 'inventory', 'financial', 'system', 'alert'];

const EventsTab = ({ gameState, onRefresh, onToast }) => {
  const { request, loading } = useAPI();
  const [events, setEvents] = useState([]);
  const [categoryFilter, setCategoryFilter] = useState('all');

  const loadEvents = async (cat) => {
    try {
      const filter = cat ?? categoryFilter;
      const endpoint =
        filter !== 'all'
          ? `${API_ENDPOINTS.game.events}?category=${filter}`
          : API_ENDPOINTS.game.events;
      const data = await request('GET', endpoint);
      setEvents(data);
    } catch (e) {
      onToast(e.message, 'error');
    }
  };

  useEffect(() => {
    loadEvents();
  }, [gameState?.current_day, categoryFilter]);

  const handleCategoryChange = (cat) => {
    setCategoryFilter(cat);
    loadEvents(cat);
  };

  const formatDetails = (details) => {
    try {
      const parsed = typeof details === 'string' ? JSON.parse(details) : details;
      return Object.entries(parsed)
        .map(([k, v]) => `${k}: ${v}`)
        .join(' · ');
    } catch {
      return details || '';
    }
  };

  // Group events by day for display
  const eventsByDay = events.reduce((acc, event) => {
    const day = event.sim_day;
    if (!acc[day]) acc[day] = [];
    acc[day].push(event);
    return acc;
  }, {});

  const sortedDays = Object.keys(eventsByDay).map(Number).sort((a, b) => b - a);

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            {categoryFilter === 'all' ? 'Total Events' : `${categoryFilter} events`}
          </p>
          <p className="text-3xl font-bold text-blue-600">{events.length}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-600 dark:text-gray-400">Current Day</p>
          <p className="text-3xl font-bold text-gray-600">{gameState?.current_day || 1}</p>
        </div>
      </div>

      {/* Category Filter */}
      <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
        <p className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-2">Filter by category</p>
        <div className="flex flex-wrap gap-2">
          {CATEGORIES.map(cat => (
            <button
              key={cat}
              onClick={() => handleCategoryChange(cat)}
              className={`px-3 py-1 rounded-full text-sm font-medium transition ${
                categoryFilter === cat
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Events Log */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center">
          <h3 className="font-bold">Event Log</h3>
          <button
            onClick={() => loadEvents()}
            disabled={loading}
            className="text-sm text-blue-600 hover:text-blue-700 disabled:text-gray-400 transition"
          >
            {loading ? 'Loading...' : 'Refresh'}
          </button>
        </div>

        {loading && events.length === 0 ? (
          <div className="p-8 text-center text-gray-500">Loading events...</div>
        ) : events.length === 0 ? (
          <div className="p-10 text-center text-gray-500 dark:text-gray-400">
            <p className="text-lg mb-1">No events yet</p>
            <p className="text-sm">Advance the day to generate simulation events.</p>
          </div>
        ) : (
          <div className="max-h-[540px] overflow-y-auto">
            {sortedDays.map(day => (
              <div key={day}>
                {/* Day Header */}
                <div className="px-4 py-2 bg-gray-50 dark:bg-gray-700 sticky top-0 z-10 border-b border-gray-200 dark:border-gray-600">
                  <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                    Day {day}
                  </span>
                  <span className="ml-2 text-xs text-gray-400 dark:text-gray-500">
                    ({eventsByDay[day].length} events)
                  </span>
                </div>

                {/* Day Events */}
                <div className="divide-y divide-gray-100 dark:divide-gray-700">
                  {eventsByDay[day].map(event => {
                    const details = formatDetails(event.details);
                    return (
                      <div key={event.event_id} className="px-4 py-3">
                        <div className="flex items-center gap-2 mb-1">
                          <span
                            className={`px-2 py-0.5 rounded-full text-xs font-medium ${CATEGORY_BADGE[event.category] || 'bg-gray-100 text-gray-800'}`}
                          >
                            {event.category}
                          </span>
                          <span className="text-sm font-medium">{event.event_type}</span>
                        </div>
                        {details && (
                          <p className="text-xs text-gray-500 dark:text-gray-400 font-mono truncate">
                            {details}
                          </p>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default EventsTab;
