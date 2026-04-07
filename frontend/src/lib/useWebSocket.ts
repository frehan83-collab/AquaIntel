"use client";

import { useEffect, useRef, useState, useCallback } from "react";

export interface WebSocketState {
  /** WebSocket is open and receiving messages */
  connected: boolean;
  /** Currently attempting to reconnect after a disconnect */
  reconnecting: boolean;
  /** Manually trigger a reconnect attempt */
  reconnect: () => void;
}

/**
 * Reusable WebSocket hook with auto-reconnect and exponential backoff.
 *
 * Usage:
 *   const { connected, reconnecting, reconnect } = useWebSocket(url, (data) => { ... });
 *
 * - Connects on mount, cleans up on unmount.
 * - On disconnect: retries with exponential backoff (1s, 2s, 4s, 8s, 16s, max 30s).
 * - Resets backoff on successful connection.
 * - Calls onMessage with the parsed JSON payload for each incoming message.
 */
export function useWebSocket(
  url: string,
  onMessage: (data: unknown) => void,
): WebSocketState {
  const [connected, setConnected] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const backoffRef = useRef(1000); // Start at 1 second
  const mountedRef = useRef(true);
  // Keep a stable ref to onMessage so we don't re-create the WS on every render
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  const clearTimer = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;
    // Don't open a second socket if one is already connecting/open
    if (
      wsRef.current &&
      (wsRef.current.readyState === WebSocket.OPEN ||
        wsRef.current.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    clearTimer();

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mountedRef.current) return;
        setConnected(true);
        setReconnecting(false);
        backoffRef.current = 1000; // Reset backoff on success
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          onMessageRef.current(payload);
        } catch {
          // Non-JSON message — ignore
        }
      };

      ws.onclose = () => {
        if (!mountedRef.current) return;
        setConnected(false);
        setReconnecting(true);
        // Schedule reconnect with exponential backoff
        const delay = backoffRef.current;
        backoffRef.current = Math.min(backoffRef.current * 2, 30_000);
        reconnectTimer.current = setTimeout(connect, delay);
      };

      ws.onerror = () => {
        // onerror is always followed by onclose — just close cleanly
        ws.close();
      };
    } catch {
      if (!mountedRef.current) return;
      setConnected(false);
      setReconnecting(true);
      const delay = backoffRef.current;
      backoffRef.current = Math.min(backoffRef.current * 2, 30_000);
      reconnectTimer.current = setTimeout(connect, delay);
    }
  }, [url, clearTimer]);

  // Manual reconnect (resets backoff)
  const reconnect = useCallback(() => {
    backoffRef.current = 1000;
    wsRef.current?.close();
    clearTimer();
    setReconnecting(true);
    connect();
  }, [connect, clearTimer]);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      clearTimer();
      wsRef.current?.close();
    };
  }, [connect, clearTimer]);

  return { connected, reconnecting, reconnect };
}
