import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import CatalogueView from './components/CatalogueView';
import CartDrawer from './components/CartDrawer';
import OrdersView from './components/OrdersView';
import AssistantView from './components/AssistantView';
import ForecastView from './components/ForecastView';
import SupplierSyncModal from './components/SupplierSyncModal';
import { getDealers } from './api';
import './App.css';

export default function App() {
  const [activeTab, setActiveTab] = useState('catalogue');
  const [dealers, setDealers] = useState([]);
  const [selectedDealerId, setSelectedDealerId] = useState(null);

  const [cartItems, setCartItems] = useState(() => {
    try {
      const saved = localStorage.getItem('vikmo_cart');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const [isCartOpen, setIsCartOpen] = useState(false);
  const [isSyncOpen, setIsSyncOpen] = useState(false);

  useEffect(() => {
    try {
      localStorage.setItem('vikmo_cart', JSON.stringify(cartItems));
    } catch {}
  }, [cartItems]);

  useEffect(() => {
    async function loadDealers() {
      try {
        const res = await getDealers();
        const list = Array.isArray(res) ? res : res.results || [];
        setDealers(list);
        if (list.length > 0) {
          setSelectedDealerId((prev) => prev || list[0].id);
        }
      } catch (err) {
        console.warn('Failed to load dealers', err);
      }
    }
    loadDealers();
  }, []);

  const selectedDealer = dealers.find((d) => d.id === selectedDealerId) || null;

  function handleAddToCart(product, quantity = 1) {
    setCartItems((prev) => {
      const existing = prev.find((item) => item.sku === product.sku);
      if (existing) {
        return prev.map((item) =>
          item.sku === product.sku
            ? { ...item, quantity: item.quantity + quantity }
            : item
        );
      }
      return [
        ...prev,
        {
          sku: product.sku,
          name: product.name,
          price: product.price,
          quantity: quantity,
        },
      ];
    });
  }

  function handleUpdateCartQty(sku, newQty) {
    if (newQty <= 0) {
      handleRemoveCartItem(sku);
      return;
    }
    setCartItems((prev) =>
      prev.map((item) => (item.sku === sku ? { ...item, quantity: newQty } : item))
    );
  }

  function handleRemoveCartItem(sku) {
    setCartItems((prev) => prev.filter((item) => item.sku !== sku));
  }

  function handleClearCart() {
    setCartItems([]);
  }

  function handleOrderCreated() {
    setActiveTab('orders');
  }

  const totalCartCount = cartItems.reduce((sum, it) => sum + it.quantity, 0);

  return (
    <div className="app-container">
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        dealers={dealers}
        selectedDealerId={selectedDealerId}
        setSelectedDealerId={setSelectedDealerId}
        cartCount={totalCartCount}
        onOpenCart={() => setIsCartOpen(true)}
        onOpenSync={() => setIsSyncOpen(true)}
      />

      <main className="main-content">
        {activeTab === 'catalogue' && (
          <CatalogueView onAddToCart={handleAddToCart} cartItems={cartItems} />
        )}

        {activeTab === 'orders' && <OrdersView dealers={dealers} />}

        {activeTab === 'assistant' && (
          <AssistantView
            selectedDealer={selectedDealer}
            onNavigateToOrders={() => setActiveTab('orders')}
          />
        )}

        {activeTab === 'forecast' && (
          <ForecastView onAddToCart={handleAddToCart} />
        )}
      </main>

      <CartDrawer
        isOpen={isCartOpen}
        onClose={() => setIsCartOpen(false)}
        cartItems={cartItems}
        onUpdateQty={handleUpdateCartQty}
        onRemoveItem={handleRemoveCartItem}
        onClearCart={handleClearCart}
        selectedDealer={selectedDealer}
        onOrderCreated={handleOrderCreated}
      />

      <SupplierSyncModal
        isOpen={isSyncOpen}
        onClose={() => setIsSyncOpen(false)}
      />

      <footer className="site-footer">
        <div className="footer-inner">
          <span>VIKMO DealerDesk B2B Platform</span>
          <span className="footer-dot">•</span>
          <span>Logged in as: {selectedDealer ? `${selectedDealer.dealer_code} - ${selectedDealer.name}` : 'None'}</span>
        </div>
      </footer>
    </div>
  );
}
