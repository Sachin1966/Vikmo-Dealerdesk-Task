import React from 'react';
import { ShoppingCart, RefreshCw, MessageSquare, Package, TrendingUp, Building2 } from 'lucide-react';

export default function Header({
  activeTab,
  setActiveTab,
  dealers,
  selectedDealerId,
  setSelectedDealerId,
  cartCount,
  onOpenCart,
  onOpenSync,
}) {
  return (
    <header className="site-header">
      <div className="header-left">
        <div className="brand-logo" onClick={() => setActiveTab('catalogue')}>
          <span className="brand-name">VIKMO</span>
          <span className="brand-divider">/</span>
          <span className="brand-product">DealerDesk</span>
        </div>

        <nav className="header-nav">
          <button
            className={`nav-btn ${activeTab === 'catalogue' ? 'active' : ''}`}
            onClick={() => setActiveTab('catalogue')}
          >
            <Package size={16} />
            <span>Catalogue</span>
          </button>

          <button
            className={`nav-btn ${activeTab === 'orders' ? 'active' : ''}`}
            onClick={() => setActiveTab('orders')}
          >
            <ShoppingCart size={16} />
            <span>Orders</span>
          </button>

          <button
            className={`nav-btn ${activeTab === 'assistant' ? 'active' : ''}`}
            onClick={() => setActiveTab('assistant')}
          >
            <MessageSquare size={16} />
            <span>AI Assistant</span>
          </button>

          <button
            className={`nav-btn ${activeTab === 'forecast' ? 'active' : ''}`}
            onClick={() => setActiveTab('forecast')}
          >
            <TrendingUp size={16} />
            <span>Forecast & Reorder</span>
          </button>
        </nav>
      </div>

      <div className="header-right">
        <button
          className="btn-secondary btn-sm"
          onClick={onOpenSync}
          title="Supplier Sync"
        >
          <RefreshCw size={14} />
          <span>Sync Supplier</span>
        </button>

        <div className="dealer-selector">
          <Building2 size={15} className="dealer-icon" />
          <select
            className="dealer-select"
            value={selectedDealerId || ''}
            onChange={(e) => setSelectedDealerId(Number(e.target.value))}
          >
            {dealers.length === 0 && <option value="">Loading dealers...</option>}
            {dealers.map((d) => (
              <option key={d.id} value={d.id}>
                {d.dealer_code} - {d.name} ({d.city})
              </option>
            ))}
          </select>
        </div>

        <button className="cart-btn" onClick={onOpenCart}>
          <ShoppingCart size={16} />
          <span>Cart</span>
          {cartCount > 0 && <span className="cart-badge">{cartCount}</span>}
        </button>
      </div>
    </header>
  );
}
