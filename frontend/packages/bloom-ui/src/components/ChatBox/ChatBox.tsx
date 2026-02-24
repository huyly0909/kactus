import { type FC, useState, useRef, useEffect } from 'react';
import {
    Card,
    TextInput,
    ActionIcon,
    ScrollArea,
    Text,
    Group,
    Stack,
    Paper,
} from '@mantine/core';
import { Send, MessageCircle } from 'lucide-react';

interface ChatMessage {
    id: string;
    content: string;
    sender: 'user' | 'system';
    timestamp: Date;
}

interface ChatBoxProps {
    messages: ChatMessage[];
    onSendMessage: (content: string) => void;
    title?: string;
    placeholder?: string;
    height?: number;
}

/**
 * ChatBox — real-time chat widget.
 * Connect with useWebSocket hook for live messaging.
 */
export const ChatBox: FC<ChatBoxProps> = ({
    messages,
    onSendMessage,
    title = 'Chat',
    placeholder = 'Type a message...',
    height = 400,
}) => {
    const [input, setInput] = useState('');
    const scrollRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom on new messages
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
        }
    }, [messages]);

    const handleSend = () => {
        const trimmed = input.trim();
        if (!trimmed) return;
        onSendMessage(trimmed);
        setInput('');
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    return (
        <Card shadow="sm" padding="md" radius="md" withBorder>
            <Group mb="sm">
                <MessageCircle size={18} />
                <Text fw={600}>{title}</Text>
            </Group>

            <ScrollArea h={height} viewportRef={scrollRef} mb="sm">
                <Stack gap="xs" p="xs">
                    {messages.map((msg) => (
                        <Paper
                            key={msg.id}
                            p="sm"
                            radius="md"
                            bg={msg.sender === 'user' ? 'indigo.0' : 'gray.0'}
                            ml={msg.sender === 'user' ? 'auto' : 0}
                            mr={msg.sender === 'system' ? 'auto' : 0}
                            maw="75%"
                        >
                            <Text size="sm">{msg.content}</Text>
                            <Text size="xs" c="dimmed" mt={2}>
                                {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </Text>
                        </Paper>
                    ))}
                </Stack>
            </ScrollArea>

            <Group gap="xs">
                <TextInput
                    flex={1}
                    placeholder={placeholder}
                    value={input}
                    onChange={(e) => setInput(e.currentTarget.value)}
                    onKeyDown={handleKeyDown}
                />
                <ActionIcon size="lg" variant="filled" color="indigo" onClick={handleSend}>
                    <Send size={16} />
                </ActionIcon>
            </Group>
        </Card>
    );
};
