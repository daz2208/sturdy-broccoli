/**
 * WebSocket Hook for SyncBoard 3.0 Real-time Features
 *
 * Provides real-time connection for:
 * - Document updates
 * - Cluster changes
 * - Job completion notifications
 * - User presence tracking
 */

import { useEffect, useRef, useCallback, useState } from 'react';
import { useAuthStore } from '@/stores/auth';
import toast from 'react-hot-toast';

/**
 * Derive WebSocket URL from API URL to avoid cross-origin issues.
 * If API is at http://192.168.1.100:8000, WS should be at ws://192.168.1.100:8000
 */
function getWebSocketURL(): string {
  // First check for explicit WS URL
  if (process.env.NEXT_PUBLIC_WS_URL) {
    return process.env.NEXT_PUBLIC_WS_URL;
  }

  // Derive from API URL
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const wsProtocol = apiUrl.startsWith('https') ? 'wss' : 'ws';
  const wsHost = apiUrl.replace(/^https?:\/\//, ''); // Remove http:// or https://

  return `${wsProtocol}://${wsHost}`;
}

const WS_URL = getWebSocketURL();

/**
 * Check if JWT token is expired
 */
function isTokenExpired(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    const expiry = payload.exp * 1000; // Convert to ms
    return Date.now() > expiry;
  } catch {
    return true; // Treat invalid tokens as expired
  }
}

export type WebSocketEventType =
  | 'connected'
  | 'disconnected'
  | 'document_created'
  | 'document_updated'
  | 'document_deleted'
  | 'cluster_created'
  | 'cluster_updated'
  | 'cluster_deleted'
  | 'clusters_reclustered'
  | 'job_started'
  | 'job_completed'
  | 'job_failed'
  | 'user_viewing'
  | 'user_left'
  | 'notification'
  | 'sync_response'
  | 'pong';

export interface WebSocketEvent {
  event: WebSocketEventType;
  data: Record<string, unknown>;
  timestamp: string;
  sender?: string;
}

export interface WebSocketState {
  isConnected: boolean;
  lastEvent: WebSocketEvent | null;
  onlineUsers: string[];
  documentViewers: Record<number, string[]>;
}

type EventHandler = (event: WebSocketEvent) => void;

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const eventHandlersRef = useRef<Map<WebSocketEventType, Set<EventHandler>>>(new Map());
  const reconnectAttemptsRef = useRef<number>(0);
  const maxReconnectAttempts = 10;
  const isConnectingRef = useRef<boolean>(false);

  const [state, setState] = useState<WebSocketState>({
    isConnected: false,
    lastEvent: null,
    onlineUsers: [],
    documentViewers: {},
  });

  const { isAuthenticated } = useAuthStore();

  // Register event handler
  const on = useCallback((eventType: WebSocketEventType, handler: EventHandler) => {
    if (!eventHandlersRef.current.has(eventType)) {
      eventHandlersRef.current.set(eventType, new Set());
    }
    eventHandlersRef.current.get(eventType)!.add(handler);

    // Return cleanup function
    return () => {
      eventHandlersRef.current.get(eventType)?.delete(handler);
    };
  }, []);

  // Send message to server
  const send = useCallback((event: string, data: Record<string, unknown> = {}) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ event, data }));
    }
  }, []);

  // Set currently viewing document
  const setViewing = useCallback((docId: number | null) => {
    if (docId) {
      send('viewing', { doc_id: docId });
    } else {
      send('left', {});
    }
  }, [send]);

  // Request sync after reconnection
  const requestSync = useCallback(() => {
    send('sync_request', {});
  }, [send]);

  // Handle incoming message
  const handleMessage = useCallback((message: WebSocketEvent) => {
    setState(prev => ({ ...prev, lastEvent: message }));

    // Update state based on event type
    switch (message.event) {
      case 'connected':
        setState(prev => ({ ...prev, isConnected: true }));
        toast.success('Connected to real-time updates');
        break;

      case 'user_viewing':
        setState(prev => ({
          ...prev,
          documentViewers: {
            ...prev.documentViewers,
            [message.data.doc_id as number]: message.data.viewers as string[],
          },
        }));
        break;

      case 'user_left':
        if (message.data.doc_id) {
          setState(prev => ({
            ...prev,
            documentViewers: {
              ...prev.documentViewers,
              [message.data.doc_id as number]: message.data.viewers as string[],
            },
          }));
        }
        if (message.data.online_users) {
          setState(prev => ({
            ...prev,
            onlineUsers: message.data.online_users as string[],
          }));
        }
        break;

      case 'sync_response':
        setState(prev => ({
          ...prev,
          onlineUsers: (message.data.online_users as string[]) || [],
        }));
        break;

      case 'notification':
        const notifType = message.data.type as string;
        const notifMessage = message.data.message as string;
        if (notifType === 'error') {
          toast.error(notifMessage);
        } else if (notifType === 'success') {
          toast.success(notifMessage);
        } else {
          toast(notifMessage);
        }
        break;

      case 'document_created':
        toast(`New document: ${message.data.title}`, { icon: '📄' });
        break;

      case 'document_deleted':
        toast(`Document deleted: #${message.data.doc_id}`, { icon: '🗑️' });
        break;

      case 'job_completed':
        toast.success(`Job completed: ${message.data.job_type}`);
        break;

      case 'job_failed':
        toast.error(`Job failed: ${message.data.job_type}`);
        break;
    }

    // Call registered handlers
    const handlers = eventHandlersRef.current.get(message.event);
    if (handlers) {
      handlers.forEach(handler => {
        try {
          handler(message);
        } catch (error) {
          console.error('WebSocket handler error:', error);
        }
      });
    }
  }, []);

  // Connect to WebSocket
  const connect = useCallback(() => {
    // Prevent multiple simultaneous connection attempts
    if (isConnectingRef.current) {
      return;
    }

    const token = localStorage.getItem('token');
    if (!token || !isAuthenticated) {
      return;
    }

    // Check if token is expired before attempting connection
    if (isTokenExpired(token)) {
      console.log('WebSocket: Token expired, not connecting');
      return;
    }

    // Clean up existing connection
    if (wsRef.current) {
      wsRef.current.close();
    }

    isConnectingRef.current = true;

    try {
      const ws = new WebSocket(`${WS_URL}/ws?token=${token}`);

      ws.onopen = () => {
        console.log('WebSocket connected');
        isConnectingRef.current = false;
        reconnectAttemptsRef.current = 0; // Reset on successful connection
        setState(prev => ({ ...prev, isConnected: true }));

        // Start ping interval (keep-alive every 30s)
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ event: 'ping', data: {} }));
          }
        }, 30000);
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as WebSocketEvent;
          handleMessage(message);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      ws.onclose = (event) => {
        console.log('WebSocket disconnected:', event.code, event.reason);
        isConnectingRef.current = false;
        setState(prev => ({ ...prev, isConnected: false }));

        // Clear ping interval
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
        }

        // Attempt reconnection with exponential backoff
        // Don't reconnect if:
        // - Intentional close (1000)
        // - Auth failure (4001)
        // - Max attempts reached
        // - Page is unloading (1001)
        const shouldReconnect =
          event.code !== 1000 &&
          event.code !== 1001 &&
          event.code !== 4001 &&
          reconnectAttemptsRef.current < maxReconnectAttempts;

        if (shouldReconnect) {
          reconnectAttemptsRef.current += 1;
          // Exponential backoff: 1s, 2s, 4s, 8s, 16s, max 30s
          const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current - 1), 30000);
          console.log(`WebSocket reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts})`);

          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        } else if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
          console.log('WebSocket: Max reconnection attempts reached');
          toast.error('Real-time connection lost. Please refresh the page.');
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        isConnectingRef.current = false;
      };

      wsRef.current = ws;
    } catch (error) {
      console.error('WebSocket connection error:', error);
      isConnectingRef.current = false;
    }
  }, [isAuthenticated, handleMessage]);

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close(1000, 'User disconnected');
      wsRef.current = null;
    }
    isConnectingRef.current = false;
    reconnectAttemptsRef.current = 0; // Reset reconnect attempts on manual disconnect
    setState(prev => ({ ...prev, isConnected: false }));
  }, []);

  // Connect when authenticated
  useEffect(() => {
    if (isAuthenticated) {
      connect();
    } else {
      disconnect();
    }

    return () => {
      disconnect();
    };
  }, [isAuthenticated, connect, disconnect]);

  return {
    ...state,
    on,
    send,
    setViewing,
    requestSync,
    connect,
    disconnect,
  };
}

export default useWebSocket;
