import React, { useState } from 'react';
import { X, Trash2, Plus, Minus, AlertCircle, ShoppingBag } from 'lucide-react';
import { createDraftOrder } from '../api';

export default function CartDrawer({
  isOpen,
  onClose,
  cartItems,
  onUpdateQty,
  onRemoveItem,
  onClearCart,
  selectedDealer,
  onOrderCreated,
}) {
  const [submitting, setSubmitting] = useState(false);
  const [errorNotice, setErrorNotice] = useState(null);

  if (!isOpen) return null;

  const lineDetails = cartItems.map((item) => {
    const unitPrice = Number(item.price);
    const lineSubtotal = Math.round(unitPrice * item.quantity * 100) / 100;
    const lineTax = Math.round(lineSubtotal * 0.18 * 100) / 100;
    const lineTotal = Math.round((lineSubtotal + lineTax) * 100) / 100;
    return {
      ...item,
      lineSubtotal,
      lineTax,
      lineTotal,
    };
  });

  const subtotal = lineDetails.reduce((sum, item) => sum + item.lineSubtotal, 0);
  const taxTotal = lineDetails.reduce((sum, item) => sum + item.lineTax, 0);
  const grandTotal = Math.round((subtotal + taxTotal) * 100) / 100;

  async function handleCheckout() {
    if (!selectedDealer) {
      setErrorNotice({
        title: 'Dealer required',
        message: 'Please select an active dealer from the top bar before creating an order.',
      });
      return;
    }

    if (cartItems.length === 0) return;

    setSubmitting(true);
    setErrorNotice(null);

    const idempotencyKey = `web-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;

    try {
      const order = await createDraftOrder(selectedDealer.id, cartItems, idempotencyKey);
      onClearCart();
      onClose();
      onOrderCreated(order);
    } catch (err) {
      setErrorNotice({
        title: err.code === 'INSUFFICIENT_STOCK' ? 'Insufficient stock' : 'Order creation failed',
        message: err.message,
        details: err.details,
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer-content" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-header">
          <div className="drawer-title">
            <ShoppingBag size={18} />
            <h2>Order Cart ({cartItems.length})</h2>
          </div>
          <button className="drawer-close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        {selectedDealer && (
          <div className="drawer-dealer-bar">
            Ordering for: <strong>{selectedDealer.dealer_code} - {selectedDealer.name}</strong>
          </div>
        )}

        {errorNotice && (
          <div className="drawer-alert">
            <AlertCircle size={16} />
            <div>
              <strong>{errorNotice.title}</strong>
              <p>{errorNotice.message}</p>
              {((Array.isArray(errorNotice.details) ? errorNotice.details : errorNotice.details?.items) || []).length > 0 && (
                <ul className="shortage-list">
                  {(Array.isArray(errorNotice.details) ? errorNotice.details : errorNotice.details.items).map((it, idx) => (
                    <li key={idx}>
                      <strong>{it.sku}</strong>: Available {it.available} / Requested {it.requested}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}

        <div className="drawer-body">
          {cartItems.length === 0 ? (
            <div className="empty-cart">
              <p>Your cart is empty.</p>
            </div>
          ) : (
            <div className="cart-list">
              {lineDetails.map((item) => (
                <div key={item.sku} className="cart-row">
                  <div className="cart-row-top">
                    <div>
                      <span className="cart-sku">{item.sku}</span>
                      <h4 className="cart-item-name">{item.name}</h4>
                    </div>
                    <button
                      className="btn-trash"
                      title="Remove"
                      onClick={() => onRemoveItem(item.sku)}
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>

                  <div className="cart-row-middle">
                    <div className="qty-picker">
                      <button
                        className="qty-btn"
                        onClick={() => onUpdateQty(item.sku, item.quantity - 1)}
                        disabled={item.quantity <= 1}
                      >
                        <Minus size={12} />
                      </button>
                      <span className="qty-number">{item.quantity}</span>
                      <button
                        className="qty-btn"
                        onClick={() => onUpdateQty(item.sku, item.quantity + 1)}
                      >
                        <Plus size={12} />
                      </button>
                    </div>

                    <div className="cart-price-block">
                      <span className="cart-unit-rate">
                        ₹{Number(item.price).toFixed(2)} × {item.quantity}
                      </span>
                      <span className="cart-subtotal-val">
                        ₹{item.lineSubtotal.toFixed(2)}
                      </span>
                    </div>
                  </div>

                  <div className="cart-tax-note">
                    18% GST: ₹{item.lineTax.toFixed(2)} (Line Total: ₹{item.lineTotal.toFixed(2)})
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {cartItems.length > 0 && (
          <div className="drawer-footer">
            <div className="summary-table">
              <div className="summary-row">
                <span>Subtotal</span>
                <span>₹{subtotal.toFixed(2)}</span>
              </div>
              <div className="summary-row">
                <span>18% GST (line rounded)</span>
                <span>₹{taxTotal.toFixed(2)}</span>
              </div>
              <div className="summary-row summary-grand">
                <span>Total Amount</span>
                <span>₹{grandTotal.toFixed(2)}</span>
              </div>
            </div>

            <button
              className="btn-primary btn-block"
              disabled={submitting}
              onClick={handleCheckout}
            >
              {submitting ? 'Creating draft order...' : 'Create Draft Order'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
