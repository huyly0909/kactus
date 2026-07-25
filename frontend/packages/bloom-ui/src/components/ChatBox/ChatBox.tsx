import { type FC, useState, useRef, useEffect } from 'react';
import { Send, MessageCircle } from 'lucide-react';
import { cn } from '../../lib/utils';

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
 * ChatBox — real-time chat widget. shadcn/Tailwind port (previously Mantine).
 * Connect with a useWebSocket hook for live messaging.
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
    <div className="rounded-lg border border-border bg-card p-4 text-card-foreground shadow-sm">
      <div className="mb-3 flex items-center gap-2">
        <MessageCircle className="h-4 w-4" />
        <span className="font-semibold">{title}</span>
      </div>

      <div
        ref={scrollRef}
        className="mb-3 space-y-2 overflow-y-auto rounded-md p-1"
        style={{ height }}
      >
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={cn(
              'max-w-[75%] rounded-md p-2',
              msg.sender === 'user' ? 'ml-auto bg-primary/10' : 'mr-auto bg-muted',
            )}
          >
            <p className="text-sm">{msg.content}</p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </p>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2">
        <input
          className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          placeholder={placeholder}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <button
          onClick={handleSend}
          className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground shadow transition-colors hover:bg-primary/90"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
};
