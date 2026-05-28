import { useState, useEffect, useRef, useCallback } from 'react';
import { Factory, Store, Truck, Play, Pause, RotateCcw, ChevronDown, ChevronRight } from 'lucide-react';
import { formatCurrency } from '../../utils/formatting';

// ─── Reusable SVG Line Chart ───────────────────────────────────────
const LineChart = ({ data, lines, yLabel, height = 200 }) => {
  if (!data || data.length === 0) return <p className="text-sm text-gray-400">No data yet</p>;

  const padding = { top: 20, right: 20, bottom: 30, left: 60 };
  const width = 500;
  const innerW = width - padding.left - padding.right;
  const innerH = height - padding.top - padding.bottom;

  const allVals = data.flatMap(d => lines.map(l => d[l.key] ?? 0));
  const minY = Math.min(0, ...allVals);
  const maxY = Math.max(1, ...allVals);
  const rangeY = maxY - minY || 1;

  const xScale = (i) => padding.left + (i / Math.max(data.length - 1, 1)) * innerW;
  const yScale = (v) => padding.top + innerH - ((v - minY) / rangeY) * innerH;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full" style={{ maxHeight: `${height}px` }}>
      {/* Grid + Y labels */}
      {[0, 0.25, 0.5, 0.75, 1].map((frac) => {
        const val = minY + frac * rangeY;
        const y = yScale(val);
        return (
          <g key={frac}>
            <line x1={padding.left} y1={y} x2={width - padding.right} y2={y} stroke="currentColor" strokeOpacity="0.1" />
            <text x={padding.left - 5} y={y + 4} textAnchor="end" className="fill-gray-400" fontSize="10">
              {maxY > 1000 ? `${(val / 1000).toFixed(1)}k` : Math.round(val).toLocaleString()}
            </text>
          </g>
        );
      })}
      {/* X labels */}
      {data.map((d, i) => {
        // Show every Nth label to avoid overlap
        const step = Math.max(1, Math.floor(data.length / 12));
        if (i % step !== 0 && i !== data.length - 1) return null;
        return (
          <text key={i} x={xScale(i)} y={height - 5} textAnchor="middle" className="fill-gray-400" fontSize="10">
            {d.day}
          </text>
        );
      })}
      {/* Lines + dots */}
      {lines.map((line) => {
        const points = data.map((d, i) => `${xScale(i)},${yScale(d[line.key] ?? 0)}`).join(' ');
        return (
          <g key={line.key}>
            <polyline points={points} fill="none" stroke={line.color} strokeWidth="2" />
            {data.map((d, i) => (
              <circle key={i} cx={xScale(i)} cy={yScale(d[line.key] ?? 0)} r="2.5" fill={line.color} />
            ))}
          </g>
        );
      })}
      {/* Legend */}
      {lines.map((line, idx) => (
        <g key={line.key}>
          <rect x={width - 160} y={5 + idx * 15} width="10" height="10" fill={line.color} rx="2" />
          <text x={width - 146} y={14 + idx * 15} className="fill-gray-400" fontSize="10">{line.label}</text>
        </g>
      ))}
      {yLabel && (
        <text x={10} y={padding.top - 5} className="fill-gray-500" fontSize="10">{yLabel}</text>
      )}
    </svg>
  );
};

// ─── Fulfillment Bar Chart ─────────────────────────────────────────
const FulfillmentChart = ({ data }) => {
  if (!data || data.length === 0) return <p className="text-sm text-gray-400">No data yet</p>;

  const padding = { top: 20, right: 20, bottom: 30, left: 40 };
  const width = 500;
  const height = 200;
  const innerW = width - padding.left - padding.right;
  const innerH = height - padding.top - padding.bottom;

  const maxVal = Math.max(1, ...data.map(d => Math.max((d.placed ?? 0), (d.fulfilled ?? 0) + (d.backordered ?? 0))));
  const barW = Math.max(4, Math.min(20, innerW / data.length / 2 - 2));
  const xScale = (i) => padding.left + (i + 0.5) * (innerW / data.length);
  const yScale = (v) => padding.top + innerH - (v / maxVal) * innerH;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full" style={{ maxHeight: '200px' }}>
      {[0, 0.5, 1].map((frac) => {
        const val = frac * maxVal;
        const y = yScale(val);
        return (
          <g key={frac}>
            <line x1={padding.left} y1={y} x2={width - padding.right} y2={y} stroke="currentColor" strokeOpacity="0.1" />
            <text x={padding.left - 5} y={y + 4} textAnchor="end" className="fill-gray-400" fontSize="10">{Math.round(val)}</text>
          </g>
        );
      })}
      {data.map((d, i) => {
        const placed = d.placed ?? 0;
        const fulfilled = d.fulfilled ?? 0;
        const backordered = d.backordered ?? 0;
        const cx = xScale(i);
        return (
          <g key={i}>
            {/* Placed (outline) */}
            {placed > 0 && (
              <rect x={cx - barW - 1} y={yScale(placed)} width={barW} height={(placed / maxVal) * innerH}
                fill="none" stroke="#60a5fa" strokeWidth="1.5" rx="2" />
            )}
            {/* Fulfilled (green) */}
            <rect x={cx + 1} y={yScale(fulfilled + backordered)} width={barW} height={(fulfilled / maxVal) * innerH}
              fill="#22c55e" rx="2" />
            {/* Backordered (red) stacked */}
            {backordered > 0 && (
              <rect x={cx + 1} y={yScale(backordered)} width={barW} height={(backordered / maxVal) * innerH}
                fill="#ef4444" rx="2" />
            )}
            {/* X label */}
            {(i % Math.max(1, Math.floor(data.length / 12)) === 0 || i === data.length - 1) && (
              <text x={cx} y={height - 5} textAnchor="middle" className="fill-gray-400" fontSize="10">{d.day}</text>
            )}
          </g>
        );
      })}
      {/* Legend */}
      <rect x={width - 140} y={5} width="10" height="10" fill="none" stroke="#60a5fa" strokeWidth="1.5" rx="2" />
      <text x={width - 126} y={14} className="fill-gray-400" fontSize="10">Placed</text>
      <rect x={width - 140} y={20} width="10" height="10" fill="#22c55e" rx="2" />
      <text x={width - 126} y={29} className="fill-gray-400" fontSize="10">Fulfilled</text>
      <rect x={width - 140} y={35} width="10" height="10" fill="#ef4444" rx="2" />
      <text x={width - 126} y={44} className="fill-gray-400" fontSize="10">Backordered</text>
    </svg>
  );
};

// ─── Scenario Events Timeline ──────────────────────────────────────
const EventsTimeline = ({ scenarioEvents, maxDay }) => {
  if (!scenarioEvents || scenarioEvents.length === 0) return <p className="text-sm text-gray-400">No scenario events</p>;

  const colors = ['#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#10b981', '#f97316'];
  const totalDays = maxDay || Math.max(...scenarioEvents.map(e => e.end_day || 25));
  const padding = { left: 60, right: 20 };
  const width = 500;
  const rowH = 28;
  const height = scenarioEvents.length * rowH + 30;
  const innerW = width - padding.left - padding.right;

  const xScale = (day) => padding.left + ((day - 1) / (totalDays - 1)) * innerW;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full" style={{ maxHeight: `${height}px` }}>
      {/* Day ticks */}
      {Array.from({ length: totalDays }, (_, i) => i + 1).map(day => {
        const step = Math.max(1, Math.floor(totalDays / 12));
        if (day % step !== 1 && day !== totalDays) return null;
        const x = xScale(day);
        return (
          <g key={day}>
            <line x1={x} y1={0} x2={x} y2={height - 20} stroke="currentColor" strokeOpacity="0.08" />
            <text x={x} y={height - 5} textAnchor="middle" className="fill-gray-400" fontSize="10">{day}</text>
          </g>
        );
      })}
      {/* Event bars */}
      {scenarioEvents.map((evt, idx) => {
        const x1 = xScale(evt.start_day);
        const x2 = xScale(evt.end_day);
        const y = idx * rowH + 4;
        const color = colors[idx % colors.length];
        return (
          <g key={idx}>
            <rect x={x1} y={y} width={Math.max(8, x2 - x1)} height={rowH - 8} fill={color} fillOpacity="0.25" stroke={color} strokeWidth="1.5" rx="4" />
            <text x={x1 + 6} y={y + rowH / 2 + 1} className="fill-current" fontSize="10" fontWeight="600" fill={color}>
              {evt.name}
            </text>
          </g>
        );
      })}
    </svg>
  );
};

// ─── Event Log Table ───────────────────────────────────────────────
const EventLogPanel = ({ events, title, color }) => {
  const [expanded, setExpanded] = useState(false);
  if (!events || events.length === 0) {
    return (
      <div className={`border-l-4 ${color} pl-3 py-2`}>
        <p className="text-sm text-gray-400">{title}: No events yet</p>
      </div>
    );
  }

  const shown = expanded ? events : events.slice(-15);

  return (
    <div className={`border-l-4 ${color}`}>
      <button
        onClick={() => setExpanded(v => !v)}
        className="flex items-center gap-2 pl-3 py-2 w-full text-left hover:bg-gray-50 dark:hover:bg-gray-700/50 transition"
      >
        {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">{title}</span>
        <span className="text-xs text-gray-400 ml-auto pr-3">{events.length} events</span>
      </button>
      <div className="pl-3 pr-1 max-h-64 overflow-y-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-gray-400 border-b border-gray-200 dark:border-gray-700">
              <th className="text-left py-1 w-12">Day</th>
              <th className="text-left py-1">Type</th>
              <th className="text-left py-1">Details</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((evt, i) => (
              <tr key={evt.id ?? i} className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                <td className="py-1 text-gray-500 font-mono">{evt.sim_day}</td>
                <td className="py-1">
                  <span className="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 font-medium">
                    {evt.event_type}
                  </span>
                </td>
                <td className="py-1 text-gray-500 dark:text-gray-400 truncate max-w-xs" title={evt.details || evt.detail || ''}>
                  {(() => {
                    const raw = evt.details || evt.detail || '';
                    if (!raw) return '-';
                    try {
                      const parsed = JSON.parse(raw);
                      return Object.entries(parsed).map(([k, v]) => `${k}: ${v}`).join(', ');
                    } catch {
                      return String(raw).slice(0, 120);
                    }
                  })()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!expanded && events.length > 15 && (
          <p className="text-xs text-gray-400 py-1 text-center">Showing last 15 of {events.length}. Click to expand.</p>
        )}
      </div>
    </div>
  );
};

// ─── Main Dashboard Component ──────────────────────────────────────
const SimDashboard = ({ gameState, onRefresh, onToast }) => {
  const [dashState, setDashState] = useState(null);
  const [loading, setLoading] = useState(false);
  const [autoRun, setAutoRun] = useState(false);
  const [scenario, setScenario] = useState('scenarios/holiday-rush.json');
  const [mode, setMode] = useState('heuristic'); // 'heuristic' or 'ai'
  const [scenarioEvents, setScenarioEvents] = useState([]);
  const [eventLogs, setEventLogs] = useState(null);
  const [showEvents, setShowEvents] = useState(false);
  const intervalRef = useRef(null);

  const fetchState = useCallback(async () => {
    try {
      const res = await fetch(`/api/dashboard/state?scenario_file=${encodeURIComponent(scenario)}`);
      if (res.ok) {
        const data = await res.json();
        setDashState(data);
      }
    } catch {
      // silently fail
    }
  }, [scenario]);

  const fetchScenarioEvents = useCallback(async () => {
    try {
      const res = await fetch(`/api/dashboard/scenario-events?scenario_file=${encodeURIComponent(scenario)}`);
      if (res.ok) setScenarioEvents(await res.json());
    } catch { /* ignore */ }
  }, [scenario]);

  const fetchEventLogs = useCallback(async () => {
    try {
      const res = await fetch('/api/dashboard/events?limit=200');
      if (res.ok) setEventLogs(await res.json());
    } catch { /* ignore */ }
  }, []);

  const runTurn = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/dashboard/run-turn?scenario_file=${encodeURIComponent(scenario)}&mode=${mode}`, {
        method: 'POST',
      });
      if (res.ok) {
        const data = await res.json();
        setDashState(data);
        if (onRefresh) onRefresh();
      }
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, [scenario, mode, onRefresh]);

  // Load state + scenario on mount and scenario change
  useEffect(() => {
    fetchState();
    fetchScenarioEvents();
  }, [fetchState, fetchScenarioEvents]);

  // Auto-run interval
  useEffect(() => {
    if (autoRun) {
      intervalRef.current = setInterval(() => { runTurn(); }, 3000);
    } else {
      if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [autoRun, runTurn]);

  const turn = dashState?.turn;
  const scenarioInfo = dashState?.scenario;
  const mfg = dashState?.manufacturer;
  const ret = dashState?.retailer;
  const prov = dashState?.provider;
  const history = dashState?.metrics_history || [];

  // --- Helpers ---
  const walletColor = (val) => {
    if (val == null) return 'text-gray-400';
    if (val > 5000) return 'text-green-500';
    if (val > 2000) return 'text-yellow-500';
    return 'text-red-500';
  };

  const sumValues = (obj) => {
    if (!obj) return 0;
    return Object.values(obj).reduce((a, b) => a + b, 0);
  };

  const topNLowest = (obj, n = 3) => {
    if (!obj) return [];
    return Object.entries(obj).sort((a, b) => a[1] - b[1]).slice(0, n);
  };

  const avgValues = (obj) => {
    if (!obj) return 0;
    const vals = Object.values(obj);
    if (vals.length === 0) return 0;
    return vals.reduce((a, b) => a + b, 0) / vals.length;
  };

  const modColor = (val, invert = false) => {
    if (val == null || val === 1.0) return 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300';
    const isExtreme = invert ? val < 0.5 : val > 2.0;
    if (isExtreme) return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200';
    return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200';
  };

  const maxDay = history.length > 0 ? Math.max(...history.map(d => d.day)) : 25;

  return (
    <div className="space-y-6">
      {/* ─── Controls Bar ─── */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Scenario:</label>
          <select
            value={scenario}
            onChange={(e) => setScenario(e.target.value)}
            className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm"
          >
            <option value="scenarios/calm-market.json">Calm Market</option>
            <option value="scenarios/holiday-rush.json">Holiday Rush</option>
          </select>
        </div>

        <div className="flex items-center gap-1 bg-gray-100 dark:bg-gray-700 rounded-lg p-1">
          <button
            onClick={() => setMode('heuristic')}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition ${
              mode === 'heuristic'
                ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-gray-100 shadow-sm'
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
            }`}
          >
            Code
          </button>
          <button
            onClick={() => setMode('ai')}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition ${
              mode === 'ai'
                ? 'bg-purple-600 text-white shadow-sm'
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
            }`}
          >
            AI Agents
          </button>
        </div>

        <button onClick={runTurn} disabled={loading}
          className={`flex items-center gap-2 px-4 py-2 ${mode === 'ai' ? 'bg-purple-600 hover:bg-purple-700' : 'bg-green-600 hover:bg-green-700'} disabled:bg-gray-400 text-white rounded-lg font-medium transition text-sm`}>
          <Play size={16} />
          {loading ? (mode === 'ai' ? 'AI Thinking...' : 'Running...') : 'Run 1 Day'}
        </button>

        <button onClick={() => setAutoRun((v) => !v)}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition text-sm ${
            autoRun
              ? 'bg-red-100 hover:bg-red-200 dark:bg-red-900 dark:hover:bg-red-800 text-red-700 dark:text-red-300'
              : 'bg-blue-100 hover:bg-blue-200 dark:bg-blue-900 dark:hover:bg-blue-800 text-blue-700 dark:text-blue-300'
          }`}>
          {autoRun ? <Pause size={16} /> : <RotateCcw size={16} />}
          {autoRun ? 'Stop' : 'Auto-Run'}
          {autoRun && (
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
            </span>
          )}
        </button>

        {/* Event Logs toggle */}
        <button onClick={() => { setShowEvents(v => !v); if (!eventLogs) fetchEventLogs(); }}
          className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 rounded-lg font-medium transition text-sm">
          {showEvents ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
          Event Logs
        </button>

        <div className="ml-auto flex items-center gap-2">
          <span className="px-3 py-1 bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200 rounded-full text-sm font-bold">
            Day {turn?.day ?? mfg?.day ?? '-'}
          </span>
        </div>
      </div>

      {/* ─── Scenario Events Banner ─── */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
        {scenarioInfo?.active_events && scenarioInfo.active_events.length > 0 ? (
          <div className="space-y-2">
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Active Scenario Events</h3>
            <div className="flex flex-wrap gap-2">
              {scenarioInfo.active_events.map((evt, i) => (
                <div key={i} className="flex items-center gap-2 px-3 py-2 bg-orange-50 dark:bg-orange-950 border border-orange-200 dark:border-orange-800 rounded-lg">
                  <span className="font-medium text-sm text-orange-800 dark:text-orange-200">{evt.name}</span>
                  {evt.description && <span className="text-xs text-orange-600 dark:text-orange-400">{evt.description}</span>}
                </div>
              ))}
            </div>
            <div className="flex flex-wrap gap-2 mt-2">
              <span className={`px-2 py-1 rounded text-xs font-medium ${modColor(scenarioInfo.demand_modifier)}`}>
                Demand: {scenarioInfo.demand_modifier?.toFixed(1) ?? '1.0'}x
              </span>
              <span className={`px-2 py-1 rounded text-xs font-medium ${modColor(scenarioInfo.supply_modifier, true)}`}>
                Supply: {scenarioInfo.supply_modifier?.toFixed(1) ?? '1.0'}x
              </span>
              <span className={`px-2 py-1 rounded text-xs font-medium ${modColor(scenarioInfo.lead_time_modifier)}`}>
                Lead Time: {scenarioInfo.lead_time_modifier?.toFixed(1) ?? '1.0'}x
              </span>
            </div>
          </div>
        ) : (
          <p className="text-sm text-gray-500 dark:text-gray-400">Normal market conditions</p>
        )}
      </div>

      {/* ─── AI Agent Output (only in AI mode) ─── */}
      {turn?.mode === 'ai' && turn?.autopilot && (
        <div className="bg-purple-50 dark:bg-purple-950 border border-purple-200 dark:border-purple-800 rounded-lg shadow p-4 space-y-3">
          <h3 className="text-sm font-semibold text-purple-800 dark:text-purple-200 flex items-center gap-2">
            <span className="inline-block w-2 h-2 rounded-full bg-purple-500 animate-pulse" />
            AI Agent Decisions (Day {turn.day})
          </h3>
          {turn.autopilot.manufacturer?.ai_output && (
            <div>
              <h4 className="text-xs font-semibold text-purple-700 dark:text-purple-300 mb-1">Manufacturer Agent</h4>
              <pre className="text-xs text-purple-900 dark:text-purple-100 bg-purple-100 dark:bg-purple-900 rounded p-2 overflow-x-auto whitespace-pre-wrap max-h-40 overflow-y-auto">
                {turn.autopilot.manufacturer.ai_output}
              </pre>
            </div>
          )}
          {turn.autopilot.retailer?.ai_output && (
            <div>
              <h4 className="text-xs font-semibold text-purple-700 dark:text-purple-300 mb-1">Retailer Agent</h4>
              <pre className="text-xs text-purple-900 dark:text-purple-100 bg-purple-100 dark:bg-purple-900 rounded p-2 overflow-x-auto whitespace-pre-wrap max-h-40 overflow-y-auto">
                {turn.autopilot.retailer.ai_output}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* ─── Three-App Status Cards ─── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Provider Card */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 border-t-4 border-blue-500">
          <div className="flex items-center gap-2 mb-3">
            <Truck size={20} className="text-blue-500" />
            <h3 className="text-lg font-bold text-gray-900 dark:text-white">Provider</h3>
          </div>
          <div className="space-y-3">
            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400">Total Stock</p>
              <p className="text-2xl font-bold text-blue-500">{sumValues(prov?.stock).toLocaleString()}</p>
              <div className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden mt-1">
                <div className="h-full bg-blue-500 transition-all" style={{ width: `${Math.min(100, (sumValues(prov?.stock) / 4000) * 100)}%` }} />
              </div>
            </div>
            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Lowest Stock Items</p>
              {topNLowest(prov?.stock).map(([name, qty]) => (
                <div key={name} className="flex justify-between text-sm">
                  <span className="text-gray-600 dark:text-gray-400 truncate">{name}</span>
                  <span className={`font-medium ${qty < 50 ? 'text-red-500' : 'text-gray-900 dark:text-gray-100'}`}>{qty}</span>
                </div>
              ))}
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-500 dark:text-gray-400">Pending Orders</span>
              <span className="font-medium text-gray-900 dark:text-gray-100">{prov?.pending_orders ?? 0}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-500 dark:text-gray-400">Avg Price</span>
              <span className="font-medium text-gray-900 dark:text-gray-100">{formatCurrency(avgValues(prov?.prices))}</span>
            </div>
          </div>
        </div>

        {/* Manufacturer Card */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 border-t-4 border-green-500">
          <div className="flex items-center gap-2 mb-3">
            <Factory size={20} className="text-green-500" />
            <h3 className="text-lg font-bold text-gray-900 dark:text-white">Manufacturer</h3>
          </div>
          <div className="space-y-3">
            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400">Wallet</p>
              <p className={`text-2xl font-bold ${walletColor(mfg?.wallet)}`}>{formatCurrency(mfg?.wallet ?? 0)}</p>
            </div>
            <div className="flex gap-4">
              <div className="flex-1">
                <p className="text-xs text-gray-500 dark:text-gray-400">Parts Stock</p>
                <p className="text-lg font-bold text-gray-900 dark:text-white">{sumValues(mfg?.parts_stock).toLocaleString()}</p>
              </div>
              <div className="flex-1">
                <p className="text-xs text-gray-500 dark:text-gray-400">Finished Goods</p>
                <p className="text-lg font-bold text-gray-900 dark:text-white">{sumValues(mfg?.finished_stock).toLocaleString()}</p>
              </div>
            </div>
            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">
                Utilisation: {((mfg?.utilisation ?? 0) * 100).toFixed(0)}%
              </p>
              <div className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                <div className={`h-full transition-all ${(mfg?.utilisation ?? 0) > 0.8 ? 'bg-red-500' : (mfg?.utilisation ?? 0) > 0.5 ? 'bg-yellow-500' : 'bg-green-500'}`}
                  style={{ width: `${Math.min(100, (mfg?.utilisation ?? 0) * 100)}%` }} />
              </div>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-500 dark:text-gray-400">Open Demands</span>
              <span className="font-medium text-gray-900 dark:text-gray-100">{mfg?.open_demands ?? 0}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-500 dark:text-gray-400">Active MOs</span>
              <span className="font-medium text-gray-900 dark:text-gray-100">{mfg?.active_mos ?? 0}</span>
            </div>
          </div>
        </div>

        {/* Retailer Card */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 border-t-4 border-purple-500">
          <div className="flex items-center gap-2 mb-3">
            <Store size={20} className="text-purple-500" />
            <h3 className="text-lg font-bold text-gray-900 dark:text-white">Retailer</h3>
          </div>
          <div className="space-y-3">
            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400">Wallet</p>
              <p className={`text-2xl font-bold ${walletColor(ret?.wallet)}`}>{formatCurrency(ret?.wallet ?? 0)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Stock per Model</p>
              {ret?.stock && Object.entries(ret.stock).map(([name, qty]) => (
                <div key={name} className="flex justify-between text-sm">
                  <span className="text-gray-600 dark:text-gray-400 truncate">{name}</span>
                  <span className="font-medium text-gray-900 dark:text-gray-100">{qty}</span>
                </div>
              ))}
              {(!ret?.stock || Object.keys(ret.stock).length === 0) && <p className="text-sm text-gray-400">No stock</p>}
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div>
                <p className="text-xs text-gray-500 dark:text-gray-400">Open</p>
                <p className="text-lg font-bold text-yellow-500">{ret?.open_orders ?? 0}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 dark:text-gray-400">Fulfilled</p>
                <p className="text-lg font-bold text-green-500">{ret?.fulfilled_orders ?? 0}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 dark:text-gray-400">Backorder</p>
                <p className="text-lg font-bold text-red-500">{ret?.backordered ?? 0}</p>
              </div>
            </div>
            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Prices</p>
              {ret?.prices && Object.entries(ret.prices).map(([name, price]) => (
                <div key={name} className="flex justify-between text-sm">
                  <span className="text-gray-600 dark:text-gray-400 truncate">{name}</span>
                  <span className="font-medium text-gray-900 dark:text-gray-100">{formatCurrency(price)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ─── Charts: 2x2 Grid ─── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* 1. Inventory Over Time */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Inventory Over Time</h3>
          <LineChart
            data={history}
            lines={[
              { key: 'parts_stock', label: 'Parts (Mfg)', color: '#3b82f6' },
              { key: 'finished_stock', label: 'Finished (Mfg)', color: '#22c55e' },
              { key: 'ret_stock', label: 'Stock (Retailer)', color: '#a855f7' },
            ]}
          />
        </div>

        {/* 2. Prices Over Time */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Prices Over Time</h3>
          <LineChart
            data={history}
            lines={[
              { key: 'provider_price', label: 'Provider (avg)', color: '#3b82f6' },
              { key: 'mfg_wholesale', label: 'Mfg Wholesale', color: '#22c55e' },
              { key: 'retailer_price', label: 'Retail Price', color: '#a855f7' },
            ]}
            yLabel="EUR"
          />
        </div>

        {/* 3. Order Fulfillment */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Order Fulfillment</h3>
          <FulfillmentChart data={history} />
        </div>

        {/* 4. Wallet Over Time */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Wallet Over Time</h3>
          <LineChart
            data={history}
            lines={[
              { key: 'mfg_wallet', label: 'Manufacturer', color: '#22c55e' },
              { key: 'ret_wallet', label: 'Retailer', color: '#a855f7' },
            ]}
            yLabel="EUR"
          />
        </div>
      </div>

      {/* ─── Scenario Events Timeline ─── */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Scenario Events Timeline</h3>
        <EventsTimeline scenarioEvents={scenarioEvents} maxDay={maxDay} />
      </div>

      {/* ─── Event Logs (collapsible) ─── */}
      {showEvents && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Event Logs (All 3 Databases)</h3>
            <button onClick={fetchEventLogs}
              className="text-xs px-2 py-1 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded text-gray-600 dark:text-gray-300 transition">
              Refresh
            </button>
          </div>
          <EventLogPanel events={eventLogs?.manufacturer} title="Manufacturer" color="border-green-500" />
          <EventLogPanel events={eventLogs?.provider} title="Provider" color="border-blue-500" />
          <EventLogPanel events={eventLogs?.retailer} title="Retailer" color="border-purple-500" />
        </div>
      )}
    </div>
  );
};

export default SimDashboard;
