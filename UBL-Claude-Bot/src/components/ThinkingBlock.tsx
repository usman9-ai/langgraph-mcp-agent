import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface ThinkingStep {
  title: string;
  content: string;
  status?: 'thinking' | 'in-progress' | 'complete' | 'error';
}

interface ThinkingBlockProps {
  steps: ThinkingStep[];
}

const ThinkingBlock: React.FC<ThinkingBlockProps> = ({ steps }) => {
  const [expandedSteps, setExpandedSteps] = useState<Set<number>>(new Set());

  const toggleStep = (index: number) => {
    const newExpanded = new Set(expandedSteps);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedSteps(newExpanded);
  };

  const getStatusIcon = (status?: string) => {
    switch (status) {
      case 'thinking':
      case 'in-progress':
        return (
          <div className="animate-spin w-4 h-4 border-2 border-accent border-t-transparent rounded-full" />
        );
      case 'complete':
        return (
          <svg className="w-4 h-4 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        );
      case 'error':
        return (
          <svg className="w-4 h-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        );
      default:
        return (
          <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        );
    }
  };

  return (
    <div className="my-4 border border-border rounded-xl overflow-hidden bg-secondary shadow-md animate-slide-in">
      {/* Header */}
      <div className="px-5 py-3.5 bg-tertiary border-b border-border flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-accent bg-opacity-10 flex items-center justify-center">
          <svg className="w-4 h-4 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
        </div>
        <span className="font-semibold text-sm text-text-primary">Thinking Process</span>
        <span className="px-2 py-1 text-xs font-medium text-accent bg-accent bg-opacity-10 rounded-full ml-auto">{steps.length} steps</span>
      </div>

      {/* Steps */}
      <div className="divide-y divide-border">
        {steps.map((step, index) => {
          const isExpanded = expandedSteps.has(index);
          
          return (
            <div key={index} className="hover:bg-tertiary transition-all duration-200 animate-fade-in">
              {/* Step Header */}
              <button
                onClick={() => toggleStep(index)}
                className="w-full px-5 py-4 flex items-center gap-4 text-left group"
              >
                {/* Status Icon */}
                <div className="flex-shrink-0">
                  {getStatusIcon(step.status)}
                </div>

                {/* Step Title */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 text-xs font-mono font-medium text-text-secondary bg-tertiary rounded">Step {index + 1}</span>
                    <span className="text-sm font-semibold text-text-primary truncate group-hover:text-accent transition-colors">{step.title}</span>
                  </div>
                </div>

                {/* Expand/Collapse Icon */}
                <svg
                  className={`w-5 h-5 text-text-secondary group-hover:text-accent transition-all duration-200 flex-shrink-0 ${
                    isExpanded ? 'rotate-90' : ''
                  }`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </button>

              {/* Step Content (Collapsible) */}
              {isExpanded && (
                <div className="px-4 pb-4 pl-11 animate-slide-in">
                  <div className="text-sm text-text-primary leading-relaxed bg-tertiary rounded-lg p-4 border border-border max-w-none">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        code({ node, inline, className, children, ...props }: any) {
                          const match = /language-(\w+)/.exec(className || '');
                          return !inline && match ? (
                            <div className="overflow-x-auto max-w-full">
                              <SyntaxHighlighter
                                style={vscDarkPlus as any}
                                language={match[1]}
                                PreTag="div"
                                wrapLines={false}
                                wrapLongLines={false}
                                customStyle={{
                                  backgroundColor: '#0B0B0B',
                                  padding: '1rem',
                                  borderRadius: '0.5rem',
                                  fontSize: '0.875rem',
                                  border: '1px solid #242424',
                                  margin: 0,
                                  whiteSpace: 'pre',
                                  overflowX: 'auto',
                                  maxWidth: '100%'
                                }}
                                codeTagProps={{
                                  style: {
                                    whiteSpace: 'pre',
                                    wordBreak: 'normal',
                                    overflowWrap: 'normal'
                                  }
                                }}
                                {...props}
                              >
                                {String(children).replace(/\n$/, '')}
                              </SyntaxHighlighter>
                            </div>
                          ) : (
                            <code className="bg-secondary px-1.5 py-0.5 rounded text-text-primary font-mono text-xs break-all" {...props}>
                              {children}
                            </code>
                          );
                        },
                        pre({ node, children, ...props }: any) {
                          return (
                            <div className="overflow-x-auto max-w-full my-2">
                              <pre className="whitespace-pre overflow-x-auto" {...props}>
                                {children}
                              </pre>
                            </div>
                          );
                        },
                      }}
                    >
                      {step.content}
                    </ReactMarkdown>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ThinkingBlock;
