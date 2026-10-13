import React, { useState, useEffect } from 'react';
import { 
  Check, 
  Truck, 
  CheckCircle, 
  X, 
  ChevronDown, 
  ChevronUp, 
  AlertCircle, 
  RefreshCw 
} from 'lucide-react';
import { getOrders, confirmOrder, dispatchOrder, deliverOrder, cancelOrder } from '../api';

export default function OrdersView({ dealers = [] }) {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState('');
  const [expandedOrders, setExpandedOrders] = useState({});
  const [actionInProgress, setActionInProgress] = useState({});
  const [actionNotice, setActionNotice] = useState(null);

  const dealerMap = React.useMemo(() => {
    return Object.fromEntries(dealers.map((d) => [d.id, d]));
  }, [dealers]);

  const fetchOrdersList = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getOrders(statusFilter);
      const list = Array.isArray(data) ? data : data.results || [];
      setOrders(list);
    } catch (err) {
      setError(err.message || 'Failed to load orders.');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchOrdersList();
  }, [fetchOrdersList]);

  function toggleExpand(orderNumber) {
    setExpandedOrders((prev) => ({
      ...prev,
      [orderNumber]: !prev[orderNumber],
    }));
  }

  async function handleAction(orderNumber, actionFn) {
    setActionInProgress((prev) => ({ ...prev, [orderNumber]: true }));
    setActionNotice(null);
    try {
      const updatedOrder = await actionFn(orderNumber);
      setActionNotice({
        type: 'success',
        message: `Order ${orderNumber} updated to ${updatedOrder.status}.`,
      });
      setOrders((prev) =>
        prev.map((o) => (o.order_number === orderNumber ? updatedOrder : o))
      );
      setTimeout(() => setActionNotice(null), 4000);
    } catch (err) {
      setActionNotice({
        type: 'error',
        message: err.message,
        details: err.details,
      });
    } finally {
      setActionInProgress((prev) => ({ ...prev, [orderNumber]: false }));
    }
  }

  return (
    <div className="orders-page">
      {/* Top Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Orders</h1>
          <p className="page-subtitle">Manage draft orders and order fulfillment lifecycles.</p>
        </div>

        <div className="filter-actions-group">
          <select
            className="filter-select"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">All statuses</option>
            <option value="DRAFT">Draft</option>
            <option value="CONFIRMED">Confirmed</option>
            <option value="DISPATCHED">Dispatched</option>
            <option value="DELIVERED">Delivered</option>
            <option value="CANCELLED">Cancelled</option>
          </select>

          <button className="btn-secondary btn-sm" onClick={fetchOrdersList} title="Refresh">
            <RefreshCw size={14} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Notifications */}
      {actionNotice && (
        <div className={`alert alert-${actionNotice.type}`}>
          <AlertCircle size={16} />
          <div>
            <span>{actionNotice.message}</span>
            {((Array.isArray(actionNotice.details) ? actionNotice.details : actionNotice.details?.items) || []).length > 0 && (
              <ul className="shortage-list">
                {(Array.isArray(actionNotice.details) ? actionNotice.details : actionNotice.details.items).map((it, idx) => (
                  <li key={idx}>
                    <strong>{it.sku}</strong>: Available {it.available} / Requested {it.requested}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {error && (
        <div className="alert alert-error">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      {/* Orders Table */}
      {loading ? (
        <div className="loading-state">
          <p>Loading orders ledger...</p>
        </div>
      ) : orders.length === 0 ? (
        <div className="empty-state">
          <p>No orders found.</p>
        </div>
      ) : (
        <div className="table-card">
          <table className="data-table">
            <thead>
              <tr>
                <th>Order Number</th>
                <th>Dealer</th>
                <th>Status</th>
                <th>Items</th>
                <th>Subtotal</th>
                <th>18% GST</th>
                <th>Grand Total</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => {
                const isExpanded = !!expandedOrders[order.order_number];
                const busy = !!actionInProgress[order.order_number];
                const status = order.status;

                return (
                  <React.Fragment key={order.order_number}>
                    <tr>
                      <td className="mono font-semibold">
                        <button
                          className="link-btn"
                          onClick={() => toggleExpand(order.order_number)}
                        >
                          {order.order_number}
                          {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                        </button>
                      </td>
                      <td>
                        <span className="font-semibold text-sm">
                          {order.dealer_code ? `${order.dealer_code} - ${order.dealer_name}` : (dealerMap[order.dealer_id] ? `${dealerMap[order.dealer_id].dealer_code} - ${dealerMap[order.dealer_id].name}` : `Dealer #${order.dealer_id}`)}
                        </span>
                      </td>
                      <td>
                        <span className={`badge badge-${status.toLowerCase()}`}>
                          {status}
                        </span>
                      </td>
                      <td>{order.items?.length || 0} items</td>
                      <td>₹{Number(order.subtotal).toFixed(2)}</td>
                      <td>₹{Number(order.tax_total).toFixed(2)}</td>
                      <td className="font-semibold">₹{Number(order.grand_total).toFixed(2)}</td>
                      <td>
                        <div className="actions-cell">
                          {status === 'DRAFT' && (
                            <>
                              <button
                                className="btn-action btn-confirm"
                                disabled={busy}
                                onClick={() => handleAction(order.order_number, confirmOrder, 'confirm')}
                              >
                                <Check size={13} />
                                <span>Confirm</span>
                              </button>
                              <button
                                className="btn-action btn-cancel"
                                disabled={busy}
                                onClick={() => handleAction(order.order_number, cancelOrder, 'cancel')}
                              >
                                <X size={13} />
                                <span>Cancel</span>
                              </button>
                            </>
                          )}

                          {status === 'CONFIRMED' && (
                            <>
                              <button
                                className="btn-action btn-dispatch"
                                disabled={busy}
                                onClick={() => handleAction(order.order_number, dispatchOrder, 'dispatch')}
                              >
                                <Truck size={13} />
                                <span>Dispatch</span>
                              </button>
                              <button
                                className="btn-action btn-cancel"
                                disabled={busy}
                                onClick={() => handleAction(order.order_number, cancelOrder, 'cancel')}
                                title="Restores inventory"
                              >
                                <X size={13} />
                                <span>Cancel & Restore</span>
                              </button>
                            </>
                          )}

                          {status === 'DISPATCHED' && (
                            <button
                              className="btn-action btn-deliver"
                              disabled={busy}
                              onClick={() => handleAction(order.order_number, deliverOrder, 'deliver')}
                            >
                              <CheckCircle size={13} />
                              <span>Deliver</span>
                            </button>
                          )}

                          {(status === 'DELIVERED' || status === 'CANCELLED') && (
                            <span className="text-muted text-sm">—</span>
                          )}
                        </div>
                      </td>
                    </tr>

                    {/* Expandable items row */}
                    {isExpanded && (
                      <tr className="subtable-row">
                        <td colSpan={8}>
                          <div className="subtable-wrap">
                            <table className="sub-table">
                              <thead>
                                <tr>
                                  <th>SKU</th>
                                  <th>Product</th>
                                  <th>Quantity</th>
                                  <th>Unit Price</th>
                                  <th>Subtotal</th>
                                  <th>18% GST</th>
                                  <th>Line Total</th>
                                </tr>
                              </thead>
                              <tbody>
                                {order.items?.map((it, idx) => (
                                  <tr key={idx}>
                                    <td className="mono">{it.sku}</td>
                                    <td>{it.product_name || it.product?.name || it.sku}</td>
                                    <td>{it.quantity}</td>
                                    <td>₹{Number(it.unit_price).toFixed(2)}</td>
                                    <td>₹{Number(it.subtotal || (it.unit_price * it.quantity)).toFixed(2)}</td>
                                    <td>₹{Number(it.tax || (it.unit_price * it.quantity * 0.18)).toFixed(2)}</td>
                                    <td className="font-semibold">
                                      ₹{Number(it.line_total || ((it.subtotal || (it.unit_price * it.quantity)) + (it.tax || 0))).toFixed(2)}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
