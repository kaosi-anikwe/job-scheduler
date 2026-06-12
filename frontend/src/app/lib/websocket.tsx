import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react';

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

export type ConnectionStatus = 'CONNECTING' | 'OPEN' | 'CLOSED';

export interface WsEvent {
  event: string;
  job_id: string;
  data: Record<string, unknown>;
  timestamp: string;
}

interface WsContextValue {
  status: ConnectionStatus;
  lastMessage: WsEvent | null;
}

/* ------------------------------------------------------------------ */
/* Context                                                             */
/* ------------------------------------------------------------------ */

const WebSocketContext = createContext<WsContextValue | undefined>(undefined);

/* ------------------------------------------------------------------ */
/* Provider                                                            */
/* ------------------------------------------------------------------ */

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [status, setStatus] = useState<ConnectionStatus>('CLOSED');
  const [lastMessage, setLastMessage] = useState<WsEvent | null>(null);
  const reconnectAttempts = useRef(0);
  const socketRef = useRef<WebSocket | null>(null);
  const mounted = useRef(true);

  const connect = useCallback(() => {
    if (!mounted.current) return;
    setStatus('CONNECTING');

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl = `${protocol}://${window.location.host}/ws/jobs`;
    const ws = new WebSocket(wsUrl);
    socketRef.current = ws;

    ws.onopen = () => {
      if (!mounted.current) return;
      setStatus('OPEN');
      reconnectAttempts.current = 0;
    };

    ws.onmessage = (event) => {
      if (!mounted.current) return;
      try {
        const payload: WsEvent = JSON.parse(event.data);
        setLastMessage(payload);
      } catch {
        // skip malformed frames
      }
    };

    ws.onclose = () => {
      if (!mounted.current) return;
      setStatus('CLOSED');
      const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);
      reconnectAttempts.current += 1;
      setTimeout(() => connect(), delay);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, []);

  useEffect(() => {
    mounted.current = true;
    connect();
    return () => {
      mounted.current = false;
      socketRef.current?.close();
    };
  }, [connect]);

  return (
    <WebSocketContext.Provider value={{ status, lastMessage }}>
      {children}
    </WebSocketContext.Provider>
  );
};

/* ------------------------------------------------------------------ */
/* Hook                                                                */
/* ------------------------------------------------------------------ */

export function useWebSocket() {
  const ctx = useContext(WebSocketContext);
  if (!ctx) throw new Error('useWebSocket must be used within WebSocketProvider');
  return ctx;
}
