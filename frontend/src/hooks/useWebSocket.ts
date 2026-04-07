'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import type { WsEvent } from '@/lib/types';

const WS_BASE =
  (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8080')
    .replace(/^http/, 'ws')
    .replace(/\/$/, '');

interface UseWebSocketOptions {
  onEvent?: (event: WsEvent) => void;
  autoConnect?: boolean;
}

export function useWebSocket(runId: string | null, options: UseWebSocketOptions = {}) {
  const [events, setEvents] = useState<WsEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const { autoConnect = true } = options;

  // Store onEvent in a ref so connect() never needs to depend on it.
  // This prevents the WebSocket from closing/reopening on every render.
  const onEventRef = useRef(options.onEvent);
  useEffect(() => {
    onEventRef.current = options.onEvent;
  });

  const connect = useCallback(() => {
    if (!runId) return;
    // Don't open a second connection if already open
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;

    const url = `${WS_BASE}/api/v1/ws/runs/${runId}/stream`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      setError(null);
    };

    ws.onmessage = (e) => {
      try {
        const raw = JSON.parse(e.data);
        // Normalise: backend sends "event" field, expose it as both event and type
        const event: WsEvent = { ...raw, type: raw.type ?? raw.event };
        setEvents((prev) => [...prev, event]);
        onEventRef.current?.(event);
      } catch {
        // ignore malformed messages
      }
    };

    ws.onerror = () => {
      setError('WebSocket connection error');
      setConnected(false);
    };

    ws.onclose = () => {
      setConnected(false);
    };
  }, [runId]); // onEvent intentionally excluded — stored in ref above

  const disconnect = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
    setConnected(false);
  }, []);

  const clearEvents = useCallback(() => setEvents([]), []);

  useEffect(() => {
    if (!autoConnect || !runId) return;
    // Small delay prevents React StrictMode double-mount from closing mid-handshake
    const timer = setTimeout(() => connect(), 100);
    return () => {
      clearTimeout(timer);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [runId, autoConnect, connect]);

  return { events, connected, error, connect, disconnect, clearEvents };
}
