import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';

export default function Chat({
  messages,
  phase,
  workflowRunning,
  workflowDone,
  pendingRequest,
  confirmSim,
  onSend,
}) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    onSend(input);
    setInput('');
  };

  const canSend =
    (!workflowRunning && !workflowDone) || pendingRequest;

  const placeholder =
    phase === 'idle'
      ? 'Describe your simulation scenario…'
      : 'Type your response…';

  return (
    <div className="chat-container">
      {/* Messages */}
      <div className="chat-messages">
        {messages.length === 0 ? (
          <div className="chat-welcome">
            <h3>👋 Welcome to DualSPHysics Simulation</h3>
            <p>Describe your simulation scenario below to get started.</p>
            <div className="example">
              <em>
                Example: Simulate a moderately dense debris flow with
                shear-thinning non-Newtonian material, 0.8 m wide and 1.0 m
                tall fluid column in a 4 m channel, density 1500 kg/m³, run
                for 2 s.
              </em>
            </div>
          </div>
        ) : (
          messages.map((msg, i) => (
            <div key={i} className={`message ${msg.role}`}>
              <div className="message-avatar">
                {msg.role === 'user' ? '👤' : '🤖'}
              </div>
              <div className="message-body">
                <div className="message-role">
                  {msg.role === 'user' ? 'You' : 'Agent'}
                </div>
                <div className="message-content">
                  <ReactMarkdown
                    skipHtml
                    components={{
                      code({ inline, className, children, ...props }) {
                        const match = /language-(\w+)/.exec(className || '');
                        if (!inline && match) {
                          return (
                            <SyntaxHighlighter
                              style={oneLight}
                              language={match[1]}
                              PreTag="div"
                              {...props}
                            >
                              {String(children).replace(/\n$/, '')}
                            </SyntaxHighlighter>
                          );
                        }
                        return (
                          <code className={className} {...props}>
                            {children}
                          </code>
                        );
                      },
                    }}
                  >
                    {msg.content}
                  </ReactMarkdown>
                </div>
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Simulation confirm buttons */}
      {confirmSim && pendingRequest && (
        <div className="confirm-sim-bar">
          <span>Ready to run the main simulation.</span>
          <button
            className="btn confirm-btn"
            onClick={() => onSend('yes')}
          >
            Run Simulation
          </button>
          <button
            className="btn decline-btn"
            onClick={() => onSend('no, I want to keep editing')}
          >
            Keep Editing
          </button>
        </div>
      )}

      {/* Input bar */}
      {!confirmSim && (
        <form className="chat-input-bar" onSubmit={handleSubmit}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={placeholder}
            disabled={!canSend}
          />
          <button type="submit" disabled={!canSend || !input.trim()}>
            Send
          </button>
        </form>
      )}
    </div>
  );
}
