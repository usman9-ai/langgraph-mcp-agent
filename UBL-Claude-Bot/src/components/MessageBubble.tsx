import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Message, useStore } from '../store/useStore';
import ThinkingBlock from './ThinkingBlock';
import MessageActions from './MessageActions';

interface MessageBubbleProps {
  message: Message;
  onRegenerate?: () => void;
  onEditComplete?: () => void;
}

const MessageBubble: React.FC<MessageBubbleProps> = ({ message, onRegenerate, onEditComplete }) => {
  const [copied, setCopied] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState(message.content);
  const { editMessage } = useStore();

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleEdit = () => {
    setIsEditing(true);
  };

  const handleSaveEdit = () => {
    if (editContent.trim()) {
      editMessage(message.id, editContent);
      setIsEditing(false);

      // Trigger regeneration if this is a user message
      if (message.role === 'user' && onEditComplete) {
        onEditComplete();
      }
    }
  };

  const handleCancelEdit = () => {
    setEditContent(message.content);
    setIsEditing(false);
  };

  // Get thinking steps from message property
  const thinkingSteps = message.thinking || [];
  const mainContent = message.content;

  const isUser = message.role === 'user';
  const proseBase =
    'prose max-w-none prose-h1:text-2xl prose-h1:font-bold prose-h1:mb-4 prose-h2:text-xl prose-h2:font-semibold prose-h2:mb-3 prose-h3:text-lg prose-h3:font-semibold prose-h3:mb-2 prose-p:leading-7 prose-p:mb-4 prose-li:mb-2 prose-strong:font-semibold prose-blockquote:border-l-4 prose-blockquote:border-accent prose-blockquote:pl-4 prose-blockquote:italic prose-table:border-collapse prose-th:border prose-th:p-2 prose-td:border prose-td:p-2 prose-a:no-underline hover:prose-a:underline';
  const proseColors = isUser
    ? 'prose-headings:text-primary prose-p:text-primary prose-li:text-primary prose-strong:text-primary prose-em:text-primary/80 prose-blockquote:text-primary/80 prose-a:text-primary'
    : 'prose-headings:text-text-primary prose-p:text-text-primary prose-li:text-text-primary prose-strong:text-text-primary prose-em:text-text-secondary prose-blockquote:text-text-secondary prose-a:text-accent';

  return (
    <div
      className={`group flex items-start gap-4 animate-slide-in hover:bg-hover hover:bg-opacity-30 -mx-4 px-4 py-3 rounded-lg transition-all duration-200 ${isUser ? 'flex-row-reverse' : ''
        }`}
    >
      {/* Avatar */}
      <div
        className={`w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 shadow-sm border transition-transform hover:scale-105 ${isUser
            ? 'bg-accent/20 text-primary border-accent/40'
            : 'bg-tertiary text-accent border-border'
          }`}
      >
        {message.role === 'user' ? (
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clipRule="evenodd" />
          </svg>
        ) : (
          <svg className="w-5 h-5 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
        )}
      </div>

      {/* Message Content */}
      <div className="flex-1 min-w-0">
        {/* Thinking Block (if present) */}
        {thinkingSteps.length > 0 && (
          <ThinkingBlock steps={thinkingSteps} />
        )}

        {isEditing ? (
          <div className="rounded-lg p-4 bg-secondary border border-accent">
            <textarea
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              className="w-full bg-primary rounded p-2 text-sm focus:outline-none min-h-[100px]"
              autoFocus
            />
            <div className="flex gap-2 mt-2">
              <button
                onClick={handleSaveEdit}
                className="px-3 py-1 bg-accent rounded text-sm hover:bg-opacity-90 transition-colors"
              >
                Save
              </button>
              <button
                onClick={handleCancelEdit}
                className="px-3 py-1 bg-secondary rounded text-sm hover:bg-hover transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div
            className={`rounded-xl p-5 transition-all duration-200 ${isUser
                ? 'bg-accent/15 border border-accent/40 text-primary ml-auto max-w-2xl shadow-sm'
                : 'bg-secondary border border-border-light shadow-sm hover:shadow-md'
              }`}
          >
            <ReactMarkdown
              className={`${proseBase} ${proseColors} ${isUser ? 'prose-th:bg-accent/20 prose-td:bg-accent/10' : 'prose-th:bg-tertiary prose-td:bg-secondary'}`}
              remarkPlugins={[remarkGfm]}
              components={{
                table({ children }: any) {
                  return (
                    <div className="overflow-x-auto my-4">
                      <table className="min-w-full border border-border">{children}</table>
                    </div>
                  );
                },
                thead({ children }: any) {
                  return <thead className={isUser ? 'bg-accent/20' : 'bg-secondary'}>{children}</thead>;
                },
                tbody({ children }: any) {
                  return <tbody className="divide-y divide-border">{children}</tbody>;
                },
                tr({ children }: any) {
                  return <tr className="border-b border-border">{children}</tr>;
                },
                th({ children }: any) {
                  return (
                    <th
                      className={`px-4 py-3 text-left text-sm font-semibold border ${isUser ? 'text-primary border-accent/40 bg-accent/20' : 'text-text-primary border-border bg-tertiary'}`}
                    >
                      {children}
                    </th>
                  );
                },
                td({ children }: any) {
                  return (
                    <td
                      className={`px-4 py-3 text-sm border ${isUser ? 'text-primary border-accent/40 bg-accent/10' : 'text-text-primary border-border bg-secondary'}`}
                    >
                      {children}
                    </td>
                  );
                },
                code({ node, className, children, ...props }: any) {
                  const match = /language-(\w+)/.exec(className || '');
                  const codeString = String(children).replace(/\n$/, '');
                  const inline = !className;

                  return !inline && match ? (
                    <div className="relative group my-2">
                      <button
                        onClick={() => copyToClipboard(codeString)}
                        className="absolute right-2 top-2 p-2 bg-hover rounded opacity-0 group-hover:opacity-100 transition-opacity"
                        title="Copy code"
                      >
                        {copied ? (
                          <svg className="w-4 h-4 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                        ) : (
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                          </svg>
                        )}
                      </button>
                      <SyntaxHighlighter
                        style={vscDarkPlus as any}
                        language={match[1]}
                        PreTag="div"
                        {...props}
                      >
                        {codeString}
                      </SyntaxHighlighter>
                    </div>
                  ) : (
                    <code
                      className={`bg-hover px-1.5 py-0.5 rounded text-sm ${isUser ? 'text-primary' : 'text-text-primary'}`}
                      {...props}
                    >
                      {children}
                    </code>
                  );
                },
              }}
            >
              {mainContent}
            </ReactMarkdown>
          </div>
        )}

        {!isEditing && (
          <div className="flex items-center justify-between mt-1 px-1">
            <span className="text-xs text-text-secondary">
              {new Date(message.timestamp).toLocaleTimeString()}
            </span>
            <MessageActions
              messageId={message.id}
              content={mainContent}
              role={message.role}
              onRegenerate={onRegenerate}
              onEdit={handleEdit}
            />
          </div>
        )}
      </div>
    </div>
  );
};

export default MessageBubble;
