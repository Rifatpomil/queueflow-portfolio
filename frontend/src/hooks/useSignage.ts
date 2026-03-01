/**
 * useSignage – subscribes to the SSE stream for a location and returns
 * the latest SignageSnapshot, updating in real time.
 */
import { useEffect, useRef, useState } from "react";
import type { SignageSnapshot } from "../types";

interface UseSignageResult {
  snapshot: SignageSnapshot | null;
  error: string | null;
  connected: boolean;
}

const BASE_URL = import.meta.env.VITE_API_URL || "";

export function useSignage(locationId: string | null): UseSignageResult {
  const [snapshot, setSnapshot] = useState<SignageSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!locationId) return;

    const url = `${BASE_URL}/v1/signage/${locationId}/stream`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => {
      setConnected(true);
      setError(null);
    };

    es.onmessage = (event) => {
      try {
        const data: SignageSnapshot = JSON.parse(event.data);
        setSnapshot(data);
      } catch {
        // Ignore parse errors (e.g., heartbeat comments parsed by some browsers)
      }
    };

    es.onerror = () => {
      setConnected(false);
      setError("Connection lost. Retrying…");
      // EventSource auto-reconnects; we just update state
    };

    return () => {
      es.close();
      setConnected(false);
    };
  }, [locationId]);

  return { snapshot, error, connected };
}
