import React, { useState, useEffect } from 'react';
import { ShoppingBag, Search, Check, AlertCircle } from 'lucide-react';
import { getReorderSuggestions } from '../api';

export default function ForecastView({ onAddToCart }) {
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState('ALL');
  const [reorderedMap, setReorderedMap] = useState({});

  const loadForecastData = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getReorderSuggestions();
      const list = Array.isArray(data) ? data : data.results || data.suggestions || [];
      setSuggestions(list);
    } catch (err) {
      setError(err.message || 'Failed to fetch reorder suggestions.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadForecastData();
  }, [loadForecastData]);

  function handleReorder(item) {
    const qty = item.reorder_qty ?? item.suggested_reorder ?? item.suggested_reorder_units ?? 10;
    if (qty <= 0) return;

    onAddToCart(
      {
        sku: item.sku,
        name: item.product_name || `Part ${item.sku}`,
        price: item.price || item.current_price || 150.0,
      },
      qty
    );

    setReorderedMap((prev) => ({ ...prev, [item.sku]: true }));
    setTimeout(() => {
      setReorderedMap((prev) => ({ ...prev, [item.sku]: false }));
    }, 1500);
  }

  const filtered = suggestions.filter((item) => {
    const matchesSearch =
      item.sku.toLowerCase().includes(search.toLowerCase()) ||
      (item.product_name && item.product_name.toLowerCase().includes(search.toLowerCase()));

    const suggestedQty = item.reorder_qty ?? item.suggested_reorder ?? item.suggested_reorder_units ?? 0;

    if (filterType === 'REORDER') {
      return matchesSearch && suggestedQty > 0;
    }
    if (filterType === 'OPTIMAL') {
      return matchesSearch && suggestedQty === 0;
    }
    return matchesSearch;
  });

  return (
    <div className="forecast-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Demand Forecast & Reorder Planning</h1>
          <p className="page-subtitle">
            4-week demand forecasts and automated safety stock reorder recommendations.
          </p>
        </div>

        <div className="formula-box">
          <span>Safety Stock: <code>⌈1.65 × σ × √L⌉</code></span>
          <span className="formula-sep">|</span>
          <span>Reorder: <code>max(0, ⌈Reorder Point - Live Stock⌉)</code></span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="filter-card">
        <div className="filter-row">
          <div className="search-input-wrap">
            <Search size={16} className="input-icon" />
            <input
              type="text"
              placeholder="Search forecast SKUs or product names..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <div className="filter-buttons">
            <button
              className={`btn-filter ${filterType === 'ALL' ? 'active' : ''}`}
              onClick={() => setFilterType('ALL')}
            >
              All SKUs ({suggestions.length})
            </button>
            <button
              className={`btn-filter ${filterType === 'REORDER' ? 'active' : ''}`}
              onClick={() => setFilterType('REORDER')}
            >
              Reorder Needed
            </button>
            <button
              className={`btn-filter ${filterType === 'OPTIMAL' ? 'active' : ''}`}
              onClick={() => setFilterType('OPTIMAL')}
            >
              Stock Adequate
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="alert alert-error">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      {/* Table view */}
      {loading ? (
        <div className="loading-state">
          <p>Calculating forecasts and safety stock levels...</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <p>No SKUs matching the current filter.</p>
        </div>
      ) : (
        <div className="table-card">
          <table className="data-table">
            <thead>
              <tr>
                <th>SKU</th>
                <th>Product</th>
                <th>Current Stock</th>
                <th>Lead Time (L)</th>
                <th>Demand σ</th>
                <th>Safety Stock</th>
                <th>Reorder Point</th>
                <th>4-Wk Forecast</th>
                <th>Suggested Reorder</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => {
                const currentStock = item.current_stock ?? item.stock ?? 0;
                const leadWeeks = item.lead_time_weeks ?? (item.lead_time_days ? item.lead_time_days / 7 : 2);
                const sigma = item.demand_std_dev ?? item.sigma ?? 0;
                const safetyStock = item.safety_stock ?? 0;
                const reorderPoint = item.reorder_point ?? 0;
                const forecast4w = item.forecast_4w ?? item.forecast_total ?? item.lead_time_demand ?? 0;
                const suggestedReorder =
                  item.reorder_qty ?? item.suggested_reorder ?? item.suggested_reorder_units ?? 0;

                const isAdded = !!reorderedMap[item.sku];

                return (
                  <tr key={item.sku}>
                    <td className="mono font-semibold">{item.sku}</td>
                    <td>{item.product_name || item.sku}</td>
                    <td>
                      <span className={`stock-pill ${currentStock === 0 ? 'stock-out' : currentStock <= 10 ? 'stock-low' : 'stock-in'}`}>
                        {currentStock} units
                      </span>
                    </td>
                    <td>{item.lead_time_days ? `${item.lead_time_days} days` : `${leadWeeks} wks`}</td>
                    <td className="mono">{Number(sigma).toFixed(1)}</td>
                    <td className="mono">{safetyStock}</td>
                    <td className="mono">{reorderPoint}</td>
                    <td className="mono font-semibold">{Number(forecast4w).toFixed(1)}</td>
                    <td>
                      {suggestedReorder > 0 ? (
                        <span className="badge badge-dispatched font-semibold">
                          +{suggestedReorder} units
                        </span>
                      ) : (
                        <span className="text-muted text-sm">Adequate</span>
                      )}
                    </td>
                    <td>
                      {suggestedReorder > 0 ? (
                        <button
                          className={`btn-sm ${isAdded ? 'btn-secondary' : 'btn-primary'}`}
                          onClick={() => handleReorder(item)}
                        >
                          {isAdded ? (
                            <>
                              <Check size={13} />
                              <span>Added</span>
                            </>
                          ) : (
                            <>
                              <ShoppingBag size={13} />
                              <span>Reorder</span>
                            </>
                          )}
                        </button>
                      ) : (
                        <span className="text-muted text-sm">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
