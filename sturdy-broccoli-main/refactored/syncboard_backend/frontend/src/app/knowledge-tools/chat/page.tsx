'use client';

import { useState, useRef, useEffect } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { Send, Trash2, Bot, User } from 'lucide-react';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

export default function KBChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async (messageText?: string) => {
    const text = messageText || input;
    if (!text.trim() || loading) return;

    const userMessage: Message = { role: 'user', content: text };
    // Capture current messages BEFORE state update for history building
    const currentMessages = [...messages];

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setSuggestions([]);
    setLoading(true);

    try {
      // Transform messages into paired format expected by backend: { user: '...', assistant: '...' }
      // Use currentMessages (snapshot) instead of messages (stale due to async state)
      const history: { user: string; assistant: string }[] = [];
      for (let i = 0; i < currentMessages.length; i += 2) {
        const userMsg = currentMessages[i];
        const assistantMsg = currentMessages[i + 1];
        if (userMsg?.role === 'user' && assistantMsg?.role === 'assistant') {
          history.push({
            user: userMsg.content,
            assistant: assistantMsg.content
          });
        }
      }

      const response = await api.knowledgeChat(text, history);

      if (!response?.response) {
        throw new Error('Invalid response from server');
      }

      const assistantMessage: Message = { role: 'assistant', content: response.response };
      setMessages(prev => [...prev, assistantMessage]);

      if (response.follow_ups && Array.isArray(response.follow_ups)) {
        setSuggestions(response.follow_ups);
      }
    } catch (err: unknown) {
      // Remove the failed user message on error to allow retry
      setMessages(prev => prev.slice(0, -1));

      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      if (errorMessage.includes('401') || errorMessage.includes('unauthorized')) {
        toast.error('Session expired. Please log in again.');
      } else if (errorMessage.includes('503') || errorMessage.includes('unavailable')) {
        toast.error('Knowledge services unavailable. Check server configuration.');
      } else if (errorMessage.includes('OpenAI') || errorMessage.includes('API key')) {
        toast.error('AI service not configured. Check OPENAI_API_KEY.');
      } else {
        toast.error('Failed to get response. Please try again.');
      }
      console.error('KB Chat error:', err);
    } finally {
      setLoading(false);
    }
  };

  const clearChat = () => {
    setMessages([]);
    setSuggestions([]);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col animate-fadeIn">
      {/* Header */}
      <div className="flex justify-between items-center mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Knowledge Base Chat</h1>
          <p className="text-gray-500">Have a conversation with your knowledge base</p>
        </div>
        <button onClick={clearChat} className="btn btn-secondary flex items-center gap-2">
          <Trash2 className="w-4 h-4" /> Clear Chat
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto bg-dark-100 rounded-xl border border-dark-300 p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-gray-500">
            <Bot className="w-16 h-16 mb-4" />
            <p className="text-lg">Start a conversation</p>
            <p className="text-sm">Ask anything about your knowledge base</p>
          </div>
        ) : (
          messages.map((msg, i) => (
            <div
              key={i}
              className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {msg.role === 'assistant' && (
                <div className="p-2 bg-accent-purple/20 rounded-full h-fit">
                  <Bot className="w-5 h-5 text-accent-purple" />
                </div>
              )}
              <div
                className={`max-w-[70%] p-4 rounded-xl ${
                  msg.role === 'user'
                    ? 'bg-primary/20 border border-primary/40'
                    : 'bg-dark-200 border border-dark-300'
                }`}
              >
                <p className="text-gray-200 whitespace-pre-wrap">{msg.content}</p>
              </div>
              {msg.role === 'user' && (
                <div className="p-2 bg-primary/20 rounded-full h-fit">
                  <User className="w-5 h-5 text-primary" />
                </div>
              )}
            </div>
          ))
        )}
        {loading && (
          <div className="flex gap-3">
            <div className="p-2 bg-accent-purple/20 rounded-full h-fit">
              <Bot className="w-5 h-5 text-accent-purple animate-pulse" />
            </div>
            <div className="bg-dark-200 border border-dark-300 p-4 rounded-xl">
              <div className="flex gap-1">
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" />
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce [animation-delay:0.1s]" />
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce [animation-delay:0.2s]" />
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Suggestions */}
      {suggestions.length > 0 && (
        <div className="flex gap-2 mt-3 flex-wrap">
          {suggestions.map((suggestion, i) => (
            <button
              key={i}
              onClick={() => sendMessage(suggestion)}
              className="px-3 py-1 text-sm bg-dark-200 border border-dark-300 rounded-full text-gray-400 hover:text-primary hover:border-primary transition-colors"
            >
              {suggestion}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="mt-4 flex gap-3">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Ask anything about your knowledge..."
          rows={1}
          className="input flex-1 resize-none"
          disabled={loading}
        />
        <button
          onClick={() => sendMessage()}
          disabled={loading || !input.trim()}
          className="btn btn-primary px-6 disabled:opacity-50"
        >
          <Send className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}
