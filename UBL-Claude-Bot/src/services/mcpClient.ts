import { useStore, STATIC_CONVERSATION_ID } from '../store/useStore';
import { buildApiUrl } from '../config/api';

export interface ChatMessage {
  message: string;
  conversation_id?: string;
}

export interface ThinkingStep {
  id?: string;
  title: string;
  content: string;
  status: 'in-progress' | 'complete' | 'error';
}

export interface ChatResponse {
  response: string;
  conversation_id: string;
  thinking?: ThinkingStep[];
}

export interface HealthResponse {
  status: string;
  mcp_connected: boolean;
  active_conversations: number;
}

export interface StreamChunk {
  type: 'thinking_step' | 'thinking_step_update' | 'thinking_step_complete' | 'content' | 'done' | 'error';
  step?: ThinkingStep;
  content?: string;
  conversation_id?: string;
}

export type StreamCallback = (chunk: StreamChunk) => void;

export class MCPClient {
  private toolSteps = new Map<string, { toolName: string; args: unknown }>();

  private buildHeaders(headers: Record<string, string> = {}) {
    const token = useStore.getState().accessToken;
    if (token) {
      return {
        ...headers,
        Authorization: `Bearer ${token}`,
      };
    }
    return headers;
  }

  async sendMessageStream(
    message: string, 
    _conversationId: string | undefined,
    _isRegenerate: boolean = false,
    onChunk: StreamCallback,
    signal?: AbortSignal
  ): Promise<void> {
    const response = await fetch(buildApiUrl('/chat'), {
      method: 'POST',
      headers: this.buildHeaders({
        'Content-Type': 'application/json',
      }),
      signal,
      body: JSON.stringify({ 
        message
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`API error (${response.status}): ${error}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('Response body is not readable');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        
        // Process complete SSE messages
        const messages = buffer.split('\n\n');
        buffer = messages.pop() || '';

        for (const rawMessage of messages) {
          const lines = rawMessage.split('\n');
          let eventName = '';
          const dataLines: string[] = [];

          for (const line of lines) {
            if (line.startsWith('event:')) {
              eventName = line.slice(6).trim();
            } else if (line.startsWith('data:')) {
              dataLines.push(line.slice(5).trim());
            }
          }

          if (!dataLines.length) {
            continue;
          }

          const data = dataLines.join('\n');
          try {
            const parsed = JSON.parse(data);
            const mappedChunks = this.mapBackendEventToUiChunks(eventName, parsed);
            for (const chunk of mappedChunks) {
              onChunk(chunk);
            }
          } catch (e) {
            console.error('Failed to parse SSE data:', data, e);
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  private mapBackendEventToUiChunks(eventName: string, payload: any): StreamChunk[] {
    const eventType = eventName || payload?.type;

    if (eventType === 'stream_open') {
      return [];
    }

    if (eventType === 'planning') {
      return [
        {
          type: 'thinking_step',
          step: {
            title: payload?.title || 'Planning & Reasoning',
            content: String(payload?.content || ''),
            status: 'complete',
          },
        },
      ];
    }

    if (eventType === 'tool_call') {
      const toolId = String(payload?.tool_id || `${payload?.tool_name || 'tool'}-${Date.now()}`);
      const toolName = String(payload?.tool_name || 'unknown');
      const args = payload?.query || {};
      this.toolSteps.set(toolId, { toolName, args });
      return [
        {
          type: 'thinking_step',
          step: {
            id: toolId,
            title: `Executing ${toolName}`,
            content: `Arguments\n\`\`\`json\n${JSON.stringify(args, null, 2)}\n\`\`\`\n\nResponse: waiting...`,
            status: 'in-progress',
          },
        },
      ];
    }

    if (eventType === 'tool_status') {
      return [];
    }

    if (eventType === 'tool_result') {
      const toolId = String(payload?.tool_id || payload?.tool_name || `tool-${Date.now()}`);
      const cached = this.toolSteps.get(toolId);
      const toolName = cached?.toolName || String(payload?.tool_name || 'unknown');
      const args = cached?.args || {};
      const rawResult = String(payload?.result || '');
      const truncated = rawResult.length > 900 ? `${rawResult.slice(0, 900)}...` : rawResult;
      return [
        {
          type: 'thinking_step_update',
          step: {
            id: toolId,
            title: `Executing ${toolName}`,
            content: `Arguments\n\`\`\`json\n${JSON.stringify(args, null, 2)}\n\`\`\`\n\nResponse\n\`\`\`text\n${truncated}\n\`\`\``,
            status: 'complete',
          },
        },
        {
          type: 'thinking_step_complete',
          step: {
            id: toolId,
            title: `Executing ${toolName}`,
            content: `Arguments\n\`\`\`json\n${JSON.stringify(args, null, 2)}\n\`\`\`\n\nResponse\n\`\`\`text\n${truncated}\n\`\`\``,
            status: 'complete',
          },
        },
      ];
    }

    if (eventType === 'final') {
      this.toolSteps.clear();
      return [
        {
          type: 'content',
          content: String(payload?.content || ''),
        },
        {
          type: 'done',
        },
      ];
    }

    if (eventType === 'error') {
      this.toolSteps.clear();
      return [
        {
          type: 'error',
          content: String(payload?.content || 'Unknown error'),
        },
      ];
    }

    return [];
  }

  async sendMessage(message: string, _conversationId?: string): Promise<ChatResponse> {
    const response = await fetch(buildApiUrl('/chat'), {
      method: 'POST',
      headers: this.buildHeaders({
        'Content-Type': 'application/json',
      }),
      body: JSON.stringify({
        message
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`API error (${response.status}): ${error}`);
    }

    return response.json();
  }

  async checkHealth(): Promise<HealthResponse> {
    const response = await fetch(buildApiUrl('/health'), {
      headers: this.buildHeaders(),
    });
    
    
    if (!response.ok) {
      throw new Error(`Health check failed: ${response.status}`);
    }
    
    return response.json();
  }

  async deleteConversation(conversationId: string = STATIC_CONVERSATION_ID): Promise<{ status: string; conversation_id: string }> {
    const response = await fetch(buildApiUrl(`/conversation/${conversationId}`), {
      method: 'DELETE',
      headers: this.buildHeaders(),
    });

    if (!response.ok) {
      throw new Error(`Failed to delete conversation: ${response.status}`);
    }

    return response.json();
  }
}

export const mcpClient = new MCPClient();
