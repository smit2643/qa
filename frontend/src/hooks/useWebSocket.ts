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
  const { onEvent, autoConnect = true } = options;

  const connect = useCallback(() => {
    if (!runId) return;

    const url = `${WS_BASE}/api/v1/ws/runs/${runId}/stream`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      setError(null);
    };

    ws.onmessage = (e) => {
      try {
        const event: WsEvent = JSON.parse(e.data);
        setEvents((prev) => [...prev, event]);
        onEvent?.(event);
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
  }, [runId, onEvent]);

  const disconnect = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
    setConnected(false);
  }, []);

  const clearEvents = useCallback(() => setEvents([]), []);

  useEffect(() => {
    if (autoConnect && runId) {
      connect();
    }
    return () => {
      wsRef.current?.close();
    };
  }, [runId, autoConnect, connect]);

  return { events, connected, error, connect, disconnect, clearEvents };
}
