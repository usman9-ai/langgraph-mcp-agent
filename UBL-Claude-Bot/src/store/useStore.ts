import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  thinking?: ThinkingStep[];
}

export interface ThinkingStep {
  id?: string;
  title: string;
  content: string;
  status?: 'thinking' | 'in-progress' | 'complete' | 'error';
}

export interface AuthUser {
  employeeId: string;
  name: string;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
  updatedAt: number;
}

export const STATIC_CONVERSATION_ID = 'conv-static-8f3d2b1a';

const createEmptyConversation = (): Conversation => ({
  id: STATIC_CONVERSATION_ID,
  title: 'New Chat',
  messages: [],
  createdAt: Date.now(),
  updatedAt: Date.now(),
});

interface StoreState {
  conversations: Conversation[];
  currentConversationId: string | null;
  currentConversation: Conversation | null;
  sidebarCollapsed: boolean;
  accessToken: string | null;
  user: AuthUser | null;
  
  createConversation: () => void;
  deleteConversation: (id: string) => void;
  setCurrentConversation: (id: string) => void;
  addMessage: (message: Omit<Message, 'id' | 'timestamp'>) => void;
  updateLastMessage: (update: Partial<Pick<Message, 'content' | 'thinking'>>) => void;
  toggleSidebar: () => void;
  updateConversationTitle: (id: string, title: string) => void;
  deleteMessage: (messageId: string) => void;
  editMessage: (messageId: string, newContent: string) => void;
  regenerateLastMessage: () => void;
  setAuth: (token: string, user: AuthUser) => void;
  clearAuth: () => void;
}

export const useStore = create<StoreState>()(
  persist(
    (set, get) => ({
      conversations: [],
      currentConversationId: null,
      currentConversation: null,
      sidebarCollapsed: false,
      accessToken: null,
      user: null,

      createConversation: () => {
        const newConversation = createEmptyConversation();
        set({
          conversations: [newConversation],
          currentConversationId: newConversation.id,
          currentConversation: newConversation,
        });
      },

      deleteConversation: (id: string) => {
        set((state) => {
          const filtered = state.conversations.filter((c) => c.id !== id);
          return {
            conversations: filtered,
            currentConversationId:
              state.currentConversationId === id
                ? filtered[0]?.id || null
                : state.currentConversationId,
            currentConversation:
              state.currentConversationId === id
                ? filtered[0] || null
                : state.currentConversation,
          };
        });
      },

      setCurrentConversation: (id: string) => {
        const conversation = get().conversations.find((c) => c.id === id);
        set({
          currentConversationId: id,
          currentConversation: conversation || null,
        });
      },

      addMessage: (message) => {
        const newMessage: Message = {
          ...message,
          id: Date.now().toString(),
          timestamp: Date.now(),
        };

        set((state) => {
          const conversations = state.conversations.map((conv) => {
            if (conv.id === state.currentConversationId) {
              const updated = {
                ...conv,
                messages: [...conv.messages, newMessage],
                updatedAt: Date.now(),
              };
              
              // Auto-generate smart title from first user message
              if (conv.title === 'New Chat' && message.role === 'user') {
                // Generate a concise title based on the message content
                const content = message.content.toLowerCase();
                
                // Check for common patterns
                if (content.includes('list') || content.includes('show') || content.includes('get')) {
                  if (content.includes('datasource') || content.includes('data source')) {
                    updated.title = 'List Datasources';
                  } else if (content.includes('workbook')) {
                    updated.title = 'List Workbooks';
                  } else if (content.includes('view')) {
                    updated.title = 'List Views';
                  } else if (content.includes('branch')) {
                    updated.title = 'Branch Analysis';
                  } else if (content.includes('top') || content.includes('highest')) {
                    updated.title = 'Top Rankings';
                  } else {
                    updated.title = message.content.slice(0, 40) + (message.content.length > 40 ? '...' : '');
                  }
                } else if (content.includes('query') || content.includes('analyze')) {
                  updated.title = 'Data Analysis';
                } else if (content.includes('how') || content.includes('what') || content.includes('why')) {
                  updated.title = message.content.slice(0, 40) + (message.content.length > 40 ? '...' : '');
                } else if (content.includes('create') || content.includes('make')) {
                  updated.title = 'Create Request';
                } else {
                  // Default: use first few words
                  const words = message.content.split(' ').slice(0, 6).join(' ');
                  updated.title = words + (message.content.split(' ').length > 6 ? '...' : '');
                }
              }
              
              return updated;
            }
            return conv;
          });

          return {
            conversations,
            currentConversation: conversations.find(
              (c) => c.id === state.currentConversationId
            ) || null,
          };
        });
      },

      updateLastMessage: (update) => {
        set((state) => {
          if (!state.currentConversation) return state;

          const conversations = state.conversations.map((conv) => {
            if (conv.id === state.currentConversationId) {
              const messages = [...conv.messages];
              if (messages.length > 0) {
                const lastMessage = messages[messages.length - 1];
                messages[messages.length - 1] = {
                  ...lastMessage,
                  ...update,
                };
              }
              return {
                ...conv,
                messages,
                updatedAt: Date.now(),
              };
            }
            return conv;
          });

          return {
            conversations,
            currentConversation: conversations.find(
              (c) => c.id === state.currentConversationId
            ) || null,
          };
        });
      },

      toggleSidebar: () => {
        set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed }));
      },

      updateConversationTitle: (id: string, title: string) => {
        set((state) => ({
          conversations: state.conversations.map((conv) =>
            conv.id === id ? { ...conv, title } : conv
          ),
        }));
      },

      deleteMessage: (messageId: string) => {
        set((state) => {
          const conversations = state.conversations.map((conv) => {
            if (conv.id === state.currentConversationId) {
              return {
                ...conv,
                messages: conv.messages.filter((msg) => msg.id !== messageId),
                updatedAt: Date.now(),
              };
            }
            return conv;
          });

          return {
            conversations,
            currentConversation: conversations.find(
              (c) => c.id === state.currentConversationId
            ) || null,
          };
        });
      },

      editMessage: (messageId: string, newContent: string) => {
        set((state) => {
          const conversations = state.conversations.map((conv) => {
            if (conv.id === state.currentConversationId) {
              return {
                ...conv,
                messages: conv.messages.map((msg) =>
                  msg.id === messageId ? { ...msg, content: newContent } : msg
                ),
                updatedAt: Date.now(),
              };
            }
            return conv;
          });

          return {
            conversations,
            currentConversation: conversations.find(
              (c) => c.id === state.currentConversationId
            ) || null,
          };
        });
      },

      regenerateLastMessage: () => {
        set((state) => {
          if (!state.currentConversation) return state;

          const messages = state.currentConversation.messages;
          if (messages.length === 0) return state;

          // Remove the last assistant message
          const lastMessage = messages[messages.length - 1];
          if (lastMessage.role !== 'assistant') return state;

          const conversations = state.conversations.map((conv) => {
            if (conv.id === state.currentConversationId) {
              return {
                ...conv,
                messages: messages.slice(0, -1),
                updatedAt: Date.now(),
              };
            }
            return conv;
          });

          return {
            conversations,
            currentConversation: conversations.find(
              (c) => c.id === state.currentConversationId
            ) || null,
          };
        });
      },

      setAuth: (token, user) => {
        set({
          accessToken: token,
          user,
        });
      },

      clearAuth: () => {
        set({
          accessToken: null,
          user: null,
          conversations: [],
          currentConversationId: null,
          currentConversation: null,
        });
      },
    }),
    {
      name: 'claude-storage',
    }
  )
);
