import React, { useState, useEffect } from 'react';
import { Search, Filter, ShoppingBag, Plus, Minus, AlertCircle, Check } from 'lucide-react';
import { getProducts } from '../api';

const CATEGORIES = ['All', 'Brakes', 'Filters', 'Transmission', 'Electrical', 'Engine', 'Chassis'];

export default function CatalogueView({ onAddToCart, cartItems }) {
  const [products, setProducts] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('All');
  const [vehicle, setVehicle] = useState('');
  const [page, setPage] = useState(1);

  const [quantities, setQuantities] = useState({});
  const [addedNotice, setAddedNotice] = useState(null);

  const fetchCatalogue = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = { page };
      if (search.trim()) params.search = search.trim();
      if (category !== 'All') params.category = category;
      if (vehicle.trim()) params.vehicle_fitment = vehicle.trim();

      const res = await getProducts(params);
      setProducts(res.results || []);
      setTotalCount(res.count || 0);
    } catch (err) {
      setError(err.message || 'Failed to load products.');
    } finally {
      setLoading(false);
    }
  }, [category, page, search, vehicle]);

  useEffect(() => {
    fetchCatalogue();
  }, [fetchCatalogue]);

  function handleQtyChange(sku, delta, maxStock) {
    setQuantities((prev) => {
      const cur = prev[sku] || 1;
      let next = cur + delta;
      if (maxStock && maxStock > 0) {
        next = Math.min(maxStock, next);
      }
      next = Math.max(1, next);
      return { ...prev, [sku]: next };
    });
  }

  function handleAdd(product) {
    if (product.stock <= 0) return;
    const qty = quantities[product.sku] || 1;
    onAddToCart(product, qty);
    setAddedNotice(product.sku);
    setTimeout(() => {
      setAddedNotice((cur) => (cur === product.sku ? null : cur));
    }, 1500);
  }

  return (
    <div className="catalogue-page">
      {/* Search and Filters Card */}
      <div className="filter-card">
        <div className="filter-row">
          <div className="search-input-wrap">
            <Search size={16} className="input-icon" />
            <input
              type="text"
              placeholder="Search by SKU, part name, or brand..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
          </div>

          <div className="fitment-input-wrap">
            <Filter size={16} className="input-icon" />
            <input
              type="text"
              placeholder="Vehicle model (e.g. Duke 390)..."
              value={vehicle}
              onChange={(e) => {
                setVehicle(e.target.value);
                setPage(1);
              }}
            />
          </div>

          <select
            className="category-select"
            value={category}
            onChange={(e) => {
              setCategory(e.target.value);
              setPage(1);
            }}
          >
            {CATEGORIES.map((cat) => (
              <option key={cat} value={cat}>
                {cat === 'All' ? 'All Categories' : cat}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Results Header */}
      <div className="catalogue-header">
        <span className="results-count">
          Showing {products.length} of {totalCount} products
        </span>
        {(search || vehicle || category !== 'All') && (
          <button
            className="clear-filters-link"
            onClick={() => {
              setSearch('');
              setVehicle('');
              setCategory('All');
              setPage(1);
            }}
          >
            Reset filters
          </button>
        )}
      </div>

      {/* Error state */}
      {error && (
        <div className="alert alert-error">
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      {/* Loading state */}
      {loading ? (
        <div className="products-grid">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="product-card skeleton-card" />
          ))}
        </div>
      ) : products.length === 0 ? (
        <div className="empty-state">
          <p>No products found matching your search criteria.</p>
        </div>
      ) : (
        <div className="products-grid">
          {products.map((p) => {
            const qty = quantities[p.sku] || 1;
            const inCart = cartItems.find((item) => item.sku === p.sku);
            const isAdded = addedNotice === p.sku;

            let stockClass = 'stock-in';
            let stockLabel = `${p.stock} in stock`;
            if (p.stock <= 0) {
              stockClass = 'stock-out';
              stockLabel = 'Out of stock';
            } else if (p.stock <= 10) {
              stockClass = 'stock-low';
              stockLabel = `Low stock: ${p.stock}`;
            }

            return (
              <div key={p.sku} className="product-card">
                <div className="product-header">
                  <div>
                    <span className="sku-badge">{p.sku}</span>
                    <span className="category-text">{p.category}</span>
                  </div>
                  <span className={`stock-pill ${stockClass}`}>{stockLabel}</span>
                </div>

                <div className="product-info">
                  <h3 className="product-name">{p.name}</h3>
                  <div className="brand-text">Brand: {p.brand}</div>
                  {p.vehicle_fitment && (
                    <div className="fitment-text">
                      Fitment: <strong>{p.vehicle_fitment}</strong>
                    </div>
                  )}
                  {p.description && (
                    <p className="product-desc" title={p.description}>
                      {p.description}
                    </p>
                  )}
                </div>

                <div className="product-footer">
                  <div className="price-box">
                    <span className="price-amount">
                      ₹{Number(p.price).toFixed(2)}
                    </span>
                    <span className="price-sub">excl. 18% GST</span>
                  </div>

                  <div className="add-action-row">
                    <div className="qty-picker">
                      <button
                        onClick={() => handleQtyChange(p.sku, -1, p.stock)}
                        disabled={qty <= 1 || p.stock <= 0}
                        className="qty-btn"
                      >
                        <Minus size={12} />
                      </button>
                      <span className="qty-number">{p.stock <= 0 ? 0 : qty}</span>
                      <button
                        onClick={() => handleQtyChange(p.sku, 1, p.stock)}
                        disabled={p.stock <= 0 || (p.stock > 0 && qty >= p.stock)}
                        className="qty-btn"
                      >
                        <Plus size={12} />
                      </button>
                    </div>

                    <button
                      className={`btn-add ${isAdded ? 'btn-added' : ''}`}
                      disabled={p.stock <= 0}
                      onClick={() => handleAdd(p)}
                    >
                      {p.stock <= 0 ? (
                        <span>Out of Stock</span>
                      ) : isAdded ? (
                        <>
                          <Check size={14} />
                          <span>Added</span>
                        </>
                      ) : (
                        <>
                          <ShoppingBag size={14} />
                          <span>Add to Cart</span>
                        </>
                      )}
                    </button>
                  </div>

                  {inCart && (
                    <div className="cart-status-text">
                      {inCart.quantity} already in cart
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Pagination */}
      {totalCount > 20 && (
        <div className="pagination">
          <button
            className="btn-page"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Previous
          </button>
          <span className="page-info">
            Page {page} of {Math.ceil(totalCount / 20)}
          </span>
          <button
            className="btn-page"
            disabled={page >= Math.ceil(totalCount / 20)}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
