import { useState, useEffect, useRef, useCallback } from 'react';

interface WebSocketMessage {
    type: string;
    payload: unknown;
}

interface UseWebSocketOptions {
    /** Auto-reconnect on disconnect (default: true) */
    reconnect?: boolean;
    /** Reconnect interval in ms (default: 3000) */
    reconnectInterval?: number;
    /** Max reconnect attempts (default: 5) */
    maxReconnectAttempts?: number;
}

interface UseWebSocketReturn {
    messages: WebSocketMessage[];
    lastMessage: WebSocketMessage | null;
    send: (data: unknown) => void;
    isConnected: boolean;
    disconnect: () => void;
}

/**
 * WebSocket hook with auto-reconnect and message buffering.
 */
export const useWebSocket = (
    url: string | null,
    options: UseWebSocketOptions = {},
): UseWebSocketReturn => {
    const {
        reconnect = true,
        reconnectInterval = 3000,
        maxReconnectAttempts = 5,
    } = options;

    const [messages, setMessages] = useState<WebSocketMessage[]>([]);
    const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
    const [isConnected, setIsConnected] = useState(false);

    const wsRef = useRef<WebSocket | null>(null);
    const reconnectAttemptsRef = useRef(0);
    const reconnectTimerRef = useRef<ReturnType<typeof setTimeout>>();

    const connect = useCallback(() => {
        if (!url) return;

        const ws = new WebSocket(url);
        wsRef.current = ws;

        ws.onopen = () => {
            setIsConnected(true);
            reconnectAttemptsRef.current = 0;
        };

        ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data) as WebSocketMessage;
                setMessages((prev) => [...prev, message]);
                setLastMessage(message);
            } catch {
                // Handle non-JSON messages
                const message: WebSocketMessage = { type: 'raw', payload: event.data };
                setMessages((prev) => [...prev, message]);
                setLastMessage(message);
            }
        };

        ws.onclose = () => {
            setIsConnected(false);
            if (reconnect && reconnectAttemptsRef.current < maxReconnectAttempts) {
                reconnectTimerRef.current = setTimeout(() => {
                    reconnectAttemptsRef.current += 1;
                    connect();
                }, reconnectInterval);
            }
        };

        ws.onerror = () => {
            ws.close();
        };
    }, [url, reconnect, reconnectInterval, maxReconnectAttempts]);

    const send = useCallback((data: unknown) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify(data));
        }
    }, []);

    const disconnect = useCallback(() => {
        clearTimeout(reconnectTimerRef.current);
        reconnectAttemptsRef.current = maxReconnectAttempts; // prevent reconnect
        wsRef.current?.close();
    }, [maxReconnectAttempts]);

    useEffect(() => {
        connect();
        return () => {
            clearTimeout(reconnectTimerRef.current);
            wsRef.current?.close();
        };
    }, [connect]);

    return { messages, lastMessage, send, isConnected, disconnect };
};
