import React, { useState, useRef, useEffect } from 'react';
import { useStore, STATIC_CONVERSATION_ID } from '../store/useStore';
import type { ThinkingStep } from '../store/useStore';
import MessageBubble from './MessageBubble';
import { mcpClient } from '../services/mcpClient';

const ChatArea: React.FC = () => {
  const { currentConversation, addMessage, createConversation, regenerateLastMessage } = useStore();
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);


  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleScroll = () => {
    if (messagesContainerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = messagesContainerRef.current;
      const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;
      setShowScrollButton(!isNearBottom);
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [currentConversation?.messages]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px';
    }
  }, [input]);

  useEffect(() => {
    if (!currentConversation || currentConversation.id !== STATIC_CONVERSATION_ID) {
      createConversation();
    }
  }, [currentConversation, createConversation]);
  const ensureConversation = () => {
    let conversation = useStore.getState().currentConversation;
    if (!conversation || conversation.id !== STATIC_CONVERSATION_ID) {
      createConversation();
      conversation = useStore.getState().currentConversation;
    }
    return conversation;
  };

  const upsertThinkingStep = (steps: ThinkingStep[], step: ThinkingStep): ThinkingStep[] => {
    if (!step.id) {
      return [...steps, step];
    }
    const idx = steps.findIndex((s) => s.id === step.id);
    if (idx === -1) {
      return [...steps, step];
    }
    const next = [...steps];
    next[idx] = step;
    return next;
  };

  const completeRunningSteps = (steps: ThinkingStep[]): ThinkingStep[] =>
    steps.map((s) => (s.status === 'in-progress' ? { ...s, status: 'complete' } : s));

  const handlePause = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const conversation = ensureConversation();
    const conversationId = conversation?.id || STATIC_CONVERSATION_ID;

    const userMessage = input.trim();
    setInput('');

    addMessage({ role: 'user', content: userMessage });
    setIsLoading(true);

    try {
      let streamedContent = '';
      let thinkingSteps: ThinkingStep[] = [];

      addMessage({
        role: 'assistant',
        content: '',
        thinking: []
      });

      await mcpClient.sendMessageStream(
        userMessage,
        conversationId,
        false,
        (chunk) => {
          const { updateLastMessage } = useStore.getState();

          switch (chunk.type) {
            case 'thinking_step':
              if (chunk.step) {
                thinkingSteps = upsertThinkingStep(thinkingSteps, chunk.step);
                updateLastMessage({ thinking: [...thinkingSteps] });
              }
              break;

            case 'thinking_step_update':
              if (chunk.step) {
                thinkingSteps = upsertThinkingStep(thinkingSteps, chunk.step);
                updateLastMessage({ thinking: [...thinkingSteps] });
              }
              break;

            case 'thinking_step_complete':
              if (chunk.step) {
                thinkingSteps = upsertThinkingStep(thinkingSteps, chunk.step);
                updateLastMessage({ thinking: [...thinkingSteps] });
              }
              break;

            case 'content':
              streamedContent += chunk.content || '';
              updateLastMessage({ content: streamedContent });
              break;

            case 'done':
              thinkingSteps = completeRunningSteps(thinkingSteps);
              updateLastMessage({ thinking: [...thinkingSteps] });
              break;

            case 'error':
              console.error('Streaming error:', chunk.content);
              updateLastMessage({
                content: `âŒ Error: ${chunk.content}`
              });
              break;
          }
        },
        (() => {
          const controller = new AbortController();
          abortControllerRef.current = controller;
          return controller.signal;
        })()
      );
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        return;
      }
      console.error('Error calling MCP API:', error);
      addMessage({
        role: 'assistant',
        content: 'âŒ Sorry, I could not reach the analytics service. Please try again.'
      });
    } finally {
      abortControllerRef.current = null;
      setIsLoading(false);
    }
  };

  const handleRegenerate = async () => {
    if (isLoading) return;

    const conversation = ensureConversation();
    if (!conversation) return;

    regenerateLastMessage();

    const messages = conversation.messages;
    const lastUserMessage = [...messages].reverse().find(m => m.role === 'user');

    if (lastUserMessage) {
      setIsLoading(true);

      try {
        let streamedContent = '';
        let thinkingSteps: ThinkingStep[] = [];

        addMessage({
          role: 'assistant',
          content: '',
          thinking: []
        });

        await mcpClient.sendMessageStream(
          lastUserMessage.content,
          conversation.id || STATIC_CONVERSATION_ID,
          true,
          (chunk) => {
            const { updateLastMessage } = useStore.getState();

            switch (chunk.type) {
              case 'thinking_step':
                if (chunk.step) {
                  thinkingSteps = upsertThinkingStep(thinkingSteps, chunk.step);
                  updateLastMessage({ thinking: [...thinkingSteps] });
                }
                break;

              case 'thinking_step_update':
                if (chunk.step) {
                  thinkingSteps = upsertThinkingStep(thinkingSteps, chunk.step);
                  updateLastMessage({ thinking: [...thinkingSteps] });
                }
                break;

              case 'thinking_step_complete':
                if (chunk.step) {
                  thinkingSteps = upsertThinkingStep(thinkingSteps, chunk.step);
                  updateLastMessage({ thinking: [...thinkingSteps] });
                }
                break;

              case 'content':
                streamedContent += chunk.content || '';
                updateLastMessage({ content: streamedContent });
                break;

              case 'done':
                thinkingSteps = completeRunningSteps(thinkingSteps);
                updateLastMessage({ thinking: [...thinkingSteps] });
                break;

              case 'error':
                console.error('Streaming error:', chunk.content);
                updateLastMessage({
                  content: `âŒ Error: ${chunk.content}`
                });
                break;
            }
          },
          (() => {
            const controller = new AbortController();
            abortControllerRef.current = controller;
            return controller.signal;
          })()
        );
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return;
        }
        console.error('Error regenerating response:', error);
        addMessage({
          role: 'assistant',
          content: 'âŒ Sorry, I could not reach the analytics service. Please try again.'
        });
      } finally {
        abortControllerRef.current = null;
        setIsLoading(false);
      }
    }
  };

  const handleEditComplete = async (messageId: string) => {
    if (isLoading || !currentConversation) return;

    // Find the edited user message
    const messageIndex = currentConversation.messages.findIndex(m => m.id === messageId);
    if (messageIndex === -1) return;

    const editedMessage = currentConversation.messages[messageIndex];

    // Find if there's an assistant message after this user message
    const nextMessage = currentConversation.messages[messageIndex + 1];

    if (nextMessage && nextMessage.role === 'assistant') {
      // Delete the old assistant response
      const { deleteMessage } = useStore.getState();
      deleteMessage(nextMessage.id);
    }

    // Generate new response using streaming
    setIsLoading(true);
    try {
      let streamedContent = '';
      let thinkingSteps: ThinkingStep[] = [];

      addMessage({
        role: 'assistant',
        content: '',
        thinking: []
      });

      await mcpClient.sendMessageStream(
        editedMessage.content,
        currentConversation?.id,
        true, // is_regenerate = true (clear conversation history for edited message)
        (chunk) => {
          const { updateLastMessage } = useStore.getState();

          switch (chunk.type) {
            case 'thinking_step':
              if (chunk.step) {
                thinkingSteps = upsertThinkingStep(thinkingSteps, chunk.step);
                updateLastMessage({ thinking: [...thinkingSteps] });
              }
              break;

            case 'thinking_step_update':
              if (chunk.step) {
                thinkingSteps = upsertThinkingStep(thinkingSteps, chunk.step);
                updateLastMessage({ thinking: [...thinkingSteps] });
              }
              break;

            case 'thinking_step_complete':
              if (chunk.step) {
                thinkingSteps = upsertThinkingStep(thinkingSteps, chunk.step);
                updateLastMessage({ thinking: [...thinkingSteps] });
              }
              break;

            case 'content':
              streamedContent += chunk.content || '';
              updateLastMessage({ content: streamedContent });
              break;

            case 'done':
              thinkingSteps = completeRunningSteps(thinkingSteps);
              updateLastMessage({ thinking: [...thinkingSteps] });
              break;

            case 'error':
              console.error('Streaming error:', chunk.content);
              updateLastMessage({
                content: `âŒ Error: ${chunk.content}`
              });
              break;
          }
        },
        (() => {
          const controller = new AbortController();
          abortControllerRef.current = controller;
          return controller.signal;
        })()
      );
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        return;
      }
      console.error('Error generating response:', error);
      addMessage({
        role: 'assistant',
        content: 'âŒ Sorry, I encountered an error. Please try again.'
      });
    } finally {
      abortControllerRef.current = null;
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="flex-1 flex flex-col bg-primary overflow-hidden relative min-h-0">
      {/* Messages Area */}
      <div
        ref={messagesContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-4 py-6 min-h-0"
      >
        {!currentConversation || currentConversation.messages.length === 0 ? (
          <div className="h-full flex items-center justify-center animate-fade-in">
            <div className="text-center max-w-md">
              <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-accent to-accent-hover flex items-center justify-center shadow-lg animate-pulse">
                <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                </svg>
              </div>
              <h2 className="text-3xl font-bold mb-3 text-text-primary">Welcome to UBL Tableau Analytics</h2>
              <p className="text-text-secondary text-lg">
                Start a conversation by typing a message below
              </p>
              <div className="mt-8 flex items-center justify-center gap-2">
                <div className="w-2 h-2 rounded-full bg-accent animate-pulse"></div>
                <p className="text-sm text-text-secondary">Connected to Tableau MCP Server</p>
              </div>
            </div>
          </div>
        ) : (
          <div className="max-w-6xl mx-auto space-y-6">
            {currentConversation.messages.map((message, index) => (
              <MessageBubble
                key={message.id}
                message={message}
                onRegenerate={message.role === 'assistant' && index === currentConversation.messages.length - 1 ? handleRegenerate : undefined}
                onEditComplete={message.role === 'user' ? () => handleEditComplete(message.id) : undefined}
              />
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Scroll to Bottom Button */}
      {showScrollButton && (
        <div className="absolute bottom-24 left-1/2 transform -translate-x-1/2 z-10">
          <button
            onClick={scrollToBottom}
            className="w-10 h-10 rounded-full bg-secondary border-2 border-border shadow-lg hover:shadow-xl flex items-center justify-center transition-all duration-200 hover:scale-110 active:scale-95 group"
            title="Scroll to bottom"
          >
            <svg
              className="w-5 h-5 text-accent group-hover:text-accent-hover transition-colors"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
            </svg>
          </button>
        </div>
      )}

      {/* Input Area */}
      <div className="border-t border-border p-4 bg-secondary backdrop-blur-sm">
        <form onSubmit={handleSubmit} className="max-w-6xl mx-auto">
          <div className="relative bg-secondary/80 rounded-xl border-2 border-border focus-within:border-accent focus-within:shadow-lg transition-all duration-200">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Message UBL Tableau Analytics..."
              className="w-full bg-transparent px-5 py-4 pr-14 resize-none focus:outline-none max-h-32 text-text-primary placeholder-text-secondary"
              rows={1}
              disabled={isLoading}
            />
            <button
              type={isLoading ? "button" : "submit"}
              onClick={isLoading ? handlePause : undefined}
              disabled={!isLoading && !input.trim()}
              className="absolute right-3 bottom-3 w-9 h-9 flex items-center justify-center rounded-lg bg-accent hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-200 shadow-sm hover:shadow-md transform hover:scale-105 active:scale-95 disabled:transform-none"
              title={isLoading ? "Pause generation" : "Send message"}
            >
              {isLoading ? (
                <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 24 24">
                  <rect x="6" y="5" width="4" height="14" rx="1"></rect>
                  <rect x="14" y="5" width="4" height="14" rx="1"></rect>
                </svg>
              ) : (
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
                </svg>
              )}
            </button>
          </div>
          <div className="flex items-center justify-center gap-2 mt-3">
            <p className="text-xs text-text-secondary">
              <kbd className="px-2 py-0.5 bg-hover rounded text-xs font-mono border border-border">Enter</kbd> to send â€¢ <kbd className="px-2 py-0.5 bg-hover rounded text-xs font-mono border border-border">Shift+Enter</kbd> for new line
            </p>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ChatArea;

