/**
 * AI-powered kiosk – natural language ticket creation.
 * Public (no auth) – for customer self-service.
 */
import { useState, useCallback } from "react";
import { useParams } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { ticketApi, aiApi } from "../api/client";

const DEMO_LOCATION_ID = "00000000-0000-0000-0000-000000000020";

export function Kiosk() {
  const { locationId } = useParams<{ locationId: string }>();
  const locId = locationId || DEMO_LOCATION_ID;
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [suggestion, setSuggestion] = useState<{
    service_id: string;
    service_name: string;
    confidence: number;
  } | null>(null);
  const [ticket, setTicket] = useState<{ id: string; display_number: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSuggest = useCallback(async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setSuggestion(null);
    try {
      const res = await aiApi.kioskSuggestService(locId, query.trim());
      if (res.suggested_service_id && res.suggested_service_name) {
        setSuggestion({
          service_id: res.suggested_service_id,
          service_name: res.suggested_service_name,
          confidence: res.confidence,
        });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "AI suggestion failed");
    } finally {
      setLoading(false);
    }
  }, [query]);

  const handleCreateTicket = useCallback(async () => {
    if (!suggestion) return;
    setLoading(true);
    setError(null);
    try {
      const t = await ticketApi.kioskCreate(locId, suggestion.service_id);
      setTicket({ id: t.id, display_number: t.display_number });
      setQuery("");
      setSuggestion(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ticket creation failed");
    } finally {
      setLoading(false);
    }
  }, [suggestion]);

  const handleReset = useCallback(() => {
    setTicket(null);
    setQuery("");
    setSuggestion(null);
    setError(null);
  }, []);

  return (
    <div className="kiosk-layout">
      <motion.div
        className="kiosk-card"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      >
        <div className="kiosk-header">
          <h1 className="kiosk-title">
            <span className="kiosk-title-icon">◆</span> QueueFlow
          </h1>
          <p className="kiosk-subtitle">AI-powered queue • Describe what you need</p>
        </div>

        <AnimatePresence mode="wait">
          {!ticket ? (
            <motion.div
              key="form"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="kiosk-form"
            >
              <div className="kiosk-input-wrap">
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSuggest()}
                  placeholder="e.g. I need to renew my driver's license"
                  className="kiosk-input"
                  autoFocus
                />
                <button
                  className="kiosk-btn kiosk-btn-primary"
                  onClick={handleSuggest}
                  disabled={loading || !query.trim()}
                >
                  {loading ? "..." : "Suggest service"}
                </button>
              </div>

              {suggestion && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  className="kiosk-suggestion"
                >
                  <div className="kiosk-suggestion-content">
                    <span className="kiosk-suggestion-label">Suggested:</span>
                    <strong>{suggestion.service_name}</strong>
                    <span className="kiosk-confidence">
                      {Math.round(suggestion.confidence * 100)}% match
                    </span>
                  </div>
                  <button
                    className="kiosk-btn kiosk-btn-success"
                    onClick={handleCreateTicket}
                    disabled={loading}
                  >
                    Get ticket →
                  </button>
                </motion.div>
              )}

              {error && (
                <motion.p
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="kiosk-error"
                >
                  {error}
                </motion.p>
              )}
            </motion.div>
          ) : (
            <motion.div
              key="success"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
              className="kiosk-success"
            >
              <div className="kiosk-success-number">{ticket.display_number}</div>
              <p className="kiosk-success-label">Your ticket number</p>
              <p className="kiosk-success-hint">Please wait to be called</p>
              <button className="kiosk-btn kiosk-btn-secondary" onClick={handleReset}>
                New ticket
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  );
}
