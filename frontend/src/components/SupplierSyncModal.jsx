import React, { useState } from 'react';
import { X, RefreshCw, CheckCircle2, AlertCircle } from 'lucide-react';
import { syncSupplier } from '../api';

export default function SupplierSyncModal({ isOpen, onClose, onSyncComplete }) {
  const [syncing, setSyncing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  async function handleTriggerSync() {
    setSyncing(true);
    setResult(null);
    setError(null);

    try {
      const data = await syncSupplier();
      setResult(data);
      if (onSyncComplete) onSyncComplete();
    } catch (err) {
      setError({
        code: err.code || 'SYNC_ERROR',
        message: err.message,
      });
    } finally {
      setSyncing(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Supplier Catalogue Synchronization</h3>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="modal-body">
          <p className="modal-desc">
            Paginates external supplier catalog feed, retries 429 rate-limits, resolves duplicate SKUs, and updates product prices without altering local stock.
          </p>

          <div className="modal-action-row">
            <button
              className="btn-primary"
              disabled={syncing}
              onClick={handleTriggerSync}
            >
              <RefreshCw size={15} className={syncing ? 'spin-icon' : ''} />
              <span>{syncing ? 'Syncing supplier catalogue...' : 'Run Sync Now'}</span>
            </button>
          </div>

          {error && (
            <div className="alert alert-error">
              <AlertCircle size={16} />
              <div>
                <strong>Sync Failed ({error.code})</strong>
                <p>{error.message}</p>
              </div>
            </div>
          )}

          {result && (
            <div className="sync-stats-card">
              <div className="sync-success-title">
                <CheckCircle2 size={16} color="var(--emerald)" />
                <span>Sync completed</span>
              </div>

              <div className="sync-grid">
                <div className="stat-item">
                  <span className="stat-num">{result.created ?? 0}</span>
                  <span className="stat-name">Created</span>
                </div>
                <div className="stat-item">
                  <span className="stat-num">{result.updated ?? 0}</span>
                  <span className="stat-name">Updated</span>
                </div>
                <div className="stat-item">
                  <span className="stat-num">{result.unchanged ?? 0}</span>
                  <span className="stat-name">Unchanged</span>
                </div>
                <div className="stat-item">
                  <span className="stat-num">
                    {Array.isArray(result.errors) ? result.errors.length : result.errors ?? 0}
                  </span>
                  <span className="stat-name">Errors</span>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
