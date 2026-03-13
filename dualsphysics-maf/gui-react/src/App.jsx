import React, { useState, useEffect, useCallback, useRef } from 'react';
import Sidebar from './components/Sidebar';
import Chat from './components/Chat';
import XmlEditor from './components/XmlEditor';
import ScriptEditor from './components/ScriptEditor';
import PythonViewer from './components/PythonViewer';
import Visualization from './components/Visualization';
import FileBrowser from './components/FileBrowser';
import FilePreview from './components/FilePreview';
import {
  fetchState,
  startWorkflow,
  respondToWorkflow,
  resetWorkflow,
  createEventSocket,
} from './api';

const PHASE_TABS = {
  idle: [{ id: 'chat', label: '💬 Chat' }],
  running: [{ id: 'chat', label: '💬 Chat' }],
  setup_review: [
    { id: 'chat', label: '💬 Chat' },
    { id: 'xml', label: '📝 XML Editor' },
    { id: 'viz', label: '🖼️ Visualization' },
  ],
  results_loop: [
    { id: 'chat', label: '💬 Chat' },
    { id: 'script', label: '📜 Shell Script' },
    { id: 'python', label: '🐍 Python Code' },
    { id: 'viz', label: '🖼️ Visualization' },
    { id: 'files', label: '📁 Files' },
  ],
  complete: [
    { id: 'chat', label: '💬 Chat' },
    { id: 'script', label: '📜 Shell Script' },
    { id: 'python', label: '🐍 Python Code' },
    { id: 'viz', label: '🖼️ Visualization' },
    { id: 'files', label: '📁 Files' },
  ],
};

export default function App() {
  const [state, setState] = useState({
    messages: [],
    phase: 'idle',
    workflow_running: false,
    workflow_done: false,
    pending_request: false,
    run_dir: null,
    files: { key_files: {}, images: [], output_files: [], python_scripts: [] },
  });
  const [activeTab, setActiveTab] = useState('chat');
  const [selectedFile, setSelectedFile] = useState(null);
  const [toast, setToast] = useState(null);
  const wsRef = useRef(null);
  const wsConnectedRef = useRef(false);
  const pollRef = useRef(null);

  // Show toast notification
  const showToast = useCallback((message, type = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  }, []);

  // Fetch initial state
  useEffect(() => {
    fetchState()
      .then((data) => setState(data))
      .catch(console.error);
  }, []);

  // Set up WebSocket for real-time events with auto-reconnect
  useEffect(() => {
    let cancelled = false;
    let reconnectTimeout = null;

    const connect = () => {
      if (cancelled) return;
      const socket = createEventSocket(
        (data) => {
          if (data.state) {
            setState((prev) => ({ ...prev, ...data.state }));
          }
        },
        () => {
          // onOpen
          wsConnectedRef.current = true;
          // Stop fallback polling when WS is connected
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
        },
        () => {
          // onClose — start fallback polling and schedule reconnect
          wsConnectedRef.current = false;
          if (!cancelled) {
            if (!pollRef.current) {
              pollRef.current = setInterval(() => {
                fetchState()
                  .then((data) => setState(data))
                  .catch(console.error);
              }, 3000);
            }
            reconnectTimeout = setTimeout(connect, 3000);
          }
        },
      );
      wsRef.current = socket;
    };

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (pollRef.current) clearInterval(pollRef.current);
      wsRef.current?.close();
    };
  }, []);

  // Handle sending a message
  const handleSend = useCallback(
    async (text) => {
      if (!text.trim()) return;

      if (!state.workflow_running && !state.workflow_done) {
        // Start new workflow
        setState((prev) => ({
          ...prev,
          messages: [...prev.messages, { role: 'user', content: text }],
          workflow_running: true,
          phase: 'running',
        }));
        try {
          await startWorkflow(text);
        } catch (err) {
          showToast(err.message, 'error');
        }
      } else if (state.pending_request) {
        // Respond to HITL request
        setState((prev) => ({
          ...prev,
          messages: [...prev.messages, { role: 'user', content: text }],
          pending_request: false,
        }));
        try {
          await respondToWorkflow(text);
        } catch (err) {
          showToast(err.message, 'error');
        }
      }

    },
    [state.workflow_running, state.workflow_done, state.pending_request, showToast]
  );

  // Handle new session
  const handleNewSession = useCallback(async () => {
    try {
      await resetWorkflow();
      const data = await fetchState();
      setState(data);
      setActiveTab('chat');
      setSelectedFile(null);
      showToast('Session reset');
    } catch (err) {
      showToast(err.message, 'error');
    }
  }, [showToast]);

  // Handle file save notification
  const handleFileSaved = useCallback(() => {
    showToast('File saved and sent to agent');
  }, [showToast]);

  const tabs = PHASE_TABS[state.phase] || PHASE_TABS.idle;
  const currentTab = tabs.find((t) => t.id === activeTab) ? activeTab : tabs[0].id;

  return (
    <div className="app-layout">
      <Sidebar
        phase={state.phase}
        workflowRunning={state.workflow_running}
        workflowDone={state.workflow_done}
        pendingRequest={state.pending_request}
        files={state.files}
        runDir={state.run_dir}
        selectedFile={selectedFile}
        onSelectFile={setSelectedFile}
        onNewSession={handleNewSession}
      />

      <div className="main-content">
        <div className="main-header">
          <h2>🌊 DualSPHysics Simulation</h2>
        </div>

        {/* Tabs */}
        {tabs.length > 1 && (
          <div className="tabs">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                className={`tab-btn ${currentTab === tab.id ? 'active' : ''}`}
                onClick={() => setActiveTab(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>
        )}

        {/* Tab content */}
        <div className="tab-content">
          {currentTab === 'chat' && (
            <Chat
              messages={state.messages}
              phase={state.phase}
              workflowRunning={state.workflow_running}
              workflowDone={state.workflow_done}
              pendingRequest={state.pending_request}
              onSend={handleSend}
            />
          )}
          {currentTab === 'xml' && (
            <XmlEditor
              xmlPath={state.files.key_files?.xml}
              onSaved={handleFileSaved}
              onError={(msg) => showToast(msg, 'error')}
            />
          )}
          {currentTab === 'script' && (
            <ScriptEditor
              scriptPath={state.files.key_files?.script}
              onSaved={handleFileSaved}
              onError={(msg) => showToast(msg, 'error')}
            />
          )}
          {currentTab === 'python' && (
            <PythonViewer scripts={state.files.python_scripts} />
          )}
          {currentTab === 'viz' && (
            <Visualization images={state.files.images} />
          )}
          {currentTab === 'files' && (
            <FileBrowser
              files={state.files.output_files}
              runDir={state.run_dir}
              selectedFile={selectedFile}
              onSelectFile={setSelectedFile}
            />
          )}
        </div>

        {/* File preview overlay */}
        {selectedFile && (
          <div className="file-preview-overlay" style={{ margin: '0 24px 16px' }}>
            <div className="file-preview-header">
              <h4>Viewing: {selectedFile.split('/').pop()}</h4>
              <button className="btn" onClick={() => setSelectedFile(null)}>
                ✕ Close
              </button>
            </div>
            <div className="file-preview-body">
              <FilePreview path={selectedFile} />
            </div>
          </div>
        )}
      </div>

      {/* Toast */}
      {toast && <div className={`toast ${toast.type}`}>{toast.message}</div>}
    </div>
  );
}
