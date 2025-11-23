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

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';

export type WebSocketEventType =
  | 'connected'
  | 'disconnected'
  | 'document_created'
  | 'document_updated'
  | 'document_deleted'
  | 'cluster_updated'
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
    const token = localStorage.getItem('token');
    if (!token || !isAuthenticated) return;

    // Clean up existing connection
    if (wsRef.current) {
      wsRef.current.close();
    }

    const ws = new WebSocket(`${WS_URL}/ws?token=${token}`);

    ws.onopen = () => {
      console.log('WebSocket connected');
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
      setState(prev => ({ ...prev, isConnected: false }));

      // Clear ping interval
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
      }

      // Attempt reconnection (unless intentional close)
      if (event.code !== 1000 && event.code !== 4001) {
        reconnectTimeoutRef.current = setTimeout(() => {
          console.log('Attempting WebSocket reconnection...');
          connect();
        }, 5000);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    wsRef.current = ws;
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
