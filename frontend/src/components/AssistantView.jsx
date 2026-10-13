import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Terminal, CheckCircle2, RotateCcw, ArrowRight } from 'lucide-react';
import { chatWithAssistant } from '../api';

const QUICK_PROMPTS = [
  'Do you have brake pads for a Duke 390?',
  'Check stock and price for BRK-1019',
  'Put 5 aside for me of BRK-1019',
  'What air filters do you recommend for Pulsar 150?',
];

export default function AssistantView({ selectedDealer, onNavigateToOrders }) {
  const [sessionId, setSessionId] = useState(() => {
    return 'sess-' + Math.random().toString(36).substring(2, 10);
  });
  const [inputMessage, setInputMessage] = useState('');
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content:
        "Hello! I am your Dealer Assistant. I can search compatible parts, check real-time stock levels, and create draft orders for you. How can I help today?",
      toolCalls: [],
      citedSkus: [],
      actions: [],
    },
  ]);
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  function resetSession() {
    const newId = 'sess-' + Math.random().toString(36).substring(2, 10);
    setSessionId(newId);
    setMessages([
      {
        role: 'assistant',
        content: "Starting a fresh session. What parts or orders would you like to inquire about?",
        toolCalls: [],
        citedSkus: [],
        actions: [],
      },
    ]);
  }

  async function handleSend(textToSend) {
    const prompt = textToSend || inputMessage;
    if (!prompt.trim() || loading) return;

    if (!selectedDealer) {
      setMessages((prev) => [
        ...prev,
        { role: 'user', content: prompt },
        {
          role: 'assistant',
          content: 'Please select a dealer from the top navigation bar to continue.',
          toolCalls: [],
          citedSkus: [],
        },
      ]);
      setInputMessage('');
      return;
    }

    const userMsg = { role: 'user', content: prompt };
    setMessages((prev) => [...prev, userMsg]);
    setInputMessage('');
    setLoading(true);

    try {
      const res = await chatWithAssistant(sessionId, selectedDealer.id, prompt);
      const assistantMsg = {
        role: 'assistant',
        content: res.message || res.reply || 'No response.',
        toolCalls: res.tool_calls || [],
        citedSkus: res.cited_skus || [],
        actions: res.actions || [],
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Error: ${err.message}`,
          toolCalls: [],
          citedSkus: [],
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="assistant-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Dealer Assistant</h1>
          <p className="page-subtitle">Natural-language inventory inquiry and automatic draft ordering.</p>
        </div>

        <button className="btn-secondary btn-sm" onClick={resetSession}>
          <RotateCcw size={14} />
          <span>New Session</span>
        </button>
      </div>

      {/* Suggested chips */}
      <div className="suggested-chips">
        <span className="suggested-label">Suggestions:</span>
        {QUICK_PROMPTS.map((qp, idx) => (
          <button
            key={idx}
            className="chip-btn"
            onClick={() => handleSend(qp)}
            disabled={loading}
          >
            {qp}
          </button>
        ))}
      </div>

      {/* Chat Box */}
      <div className="chat-card">
        <div className="chat-history">
          {messages.map((m, idx) => (
            <div key={idx} className={`chat-message ${m.role}`}>
              <div className="message-avatar">
                {m.role === 'assistant' ? <Bot size={16} /> : <User size={16} />}
              </div>

              <div className="message-content">
                <div className="message-bubble">
                  {m.content.split('\n').map((line, lIdx) => (
                    <p key={lIdx}>{line}</p>
                  ))}
                </div>

                {/* Referenced SKUs */}
                {m.citedSkus?.length > 0 && (
                  <div className="cited-row">
                    <span className="cited-text">SKUs referenced:</span>
                    {m.citedSkus.map((sku, sIdx) => (
                      <span key={sIdx} className="sku-tag">
                        {sku}
                      </span>
                    ))}
                  </div>
                )}

                {/* Tool calls output */}
                {m.toolCalls?.length > 0 && (
                  <div className="tool-box">
                    <div className="tool-box-header">
                      <Terminal size={13} />
                      <span>Database tools called ({m.toolCalls.length})</span>
                    </div>
                    {m.toolCalls.map((tc, tcIdx) => (
                      <div key={tcIdx} className="tool-item">
                        <code>{tc.tool || tc.function?.name}()</code>
                        <span className="tool-args-text">
                          {JSON.stringify(tc.arguments || tc.function?.arguments || {})}
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Draft Order Created */}
                {m.actions?.map((act, aIdx) => {
                  if (act.type === 'draft_order_created' || act.order_number) {
                    return (
                      <div key={aIdx} className="order-notice-box">
                        <CheckCircle2 size={16} color="var(--emerald)" />
                        <span>Draft order <strong>{act.order_number}</strong> created.</span>
                        <button
                          className="link-btn inline-link"
                          onClick={() => onNavigateToOrders(act.order_number)}
                        >
                          View in Orders <ArrowRight size={13} />
                        </button>
                      </div>
                    );
                  }
                  return null;
                })}
              </div>
            </div>
          ))}

          {loading && (
            <div className="chat-message assistant">
              <div className="message-avatar"><Bot size={16} /></div>
              <div className="message-content">
                <div className="message-bubble typing-bubble">
                  <span>Assistant is typing...</span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="chat-input-row">
          <input
            type="text"
            className="chat-input"
            placeholder={
              selectedDealer
                ? `Ask about parts or ordering for ${selectedDealer.name}...`
                : 'Select a dealer to begin...'
            }
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            disabled={loading}
          />
          <button
            className="btn-primary"
            onClick={() => handleSend()}
            disabled={loading || !inputMessage.trim()}
          >
            <Send size={15} />
            <span>Send</span>
          </button>
        </div>
      </div>
    </div>
  );
}
