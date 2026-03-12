import React from 'react';

const PHASE_LABELS = {
  idle: { label: 'Ready', icon: '⚪' },
  running: { label: 'Processing…', icon: '🔄' },
  setup_review: { label: 'Setup Review', icon: '🔍' },
  results_loop: { label: 'Post-Processing', icon: '📊' },
  complete: { label: 'Complete', icon: '✅' },
};

function fileIcon(path) {
  const ext = path.split('.').pop().toLowerCase();
  return (
    {
      png: '🖼️', jpg: '🖼️', jpeg: '🖼️',
      csv: '📊', vtk: '📦', bi4: '📦',
      py: '🐍', xml: '📝', sh: '📜', txt: '📄',
    }[ext] || '📄'
  );
}

export default function Sidebar({
  phase,
  workflowRunning,
  workflowDone,
  pendingRequest,
  files,
  runDir,
  selectedFile,
  onSelectFile,
  onNewSession,
}) {
  const phaseInfo = PHASE_LABELS[phase] || PHASE_LABELS.idle;
  const { key_files = {}, images = [], output_files = [], python_scripts = [] } = files || {};

  return (
    <aside className="sidebar">
      {/* Header */}
      <div className="sidebar-header">
        <h1>🌊 DualSPHysics</h1>
        <div className={`phase-badge ${phase}`}>
          <span>{phaseInfo.icon}</span>
          <span>{phaseInfo.label}</span>
        </div>
      </div>

      {/* Agent working indicator */}
      {workflowRunning && !pendingRequest && (
        <div className="agent-working">
          <div className="spinner" />
          Agent is working…
        </div>
      )}

      {/* New Session button */}
      {workflowDone && (
        <button className="new-session-btn" onClick={onNewSession}>
          🔄 New Session
        </button>
      )}

      {/* Key Files */}
      {(key_files.xml || key_files.script) && (
        <div className="sidebar-section">
          <h3>📌 Key Files</h3>
          {key_files.xml && (
            <button
              className={`sidebar-btn ${selectedFile === key_files.xml ? 'active' : ''}`}
              onClick={() => onSelectFile(key_files.xml)}
            >
              📝 Case_Def.xml
            </button>
          )}
          {key_files.script && (
            <button
              className={`sidebar-btn ${selectedFile === key_files.script ? 'active' : ''}`}
              onClick={() => onSelectFile(key_files.script)}
            >
              📜 postprocess.sh
            </button>
          )}
        </div>
      )}

      {/* Generated Files */}
      {(images.length > 0 || python_scripts.length > 0 || output_files.length > 0) && (
        <div className="sidebar-section">
          <h3>📁 Generated Files</h3>

          {images.length > 0 && (
            <details className="sidebar-expander">
              <summary>🖼️ Images ({images.length})</summary>
              <div className="sidebar-expander-content">
                {images.map((img) => (
                  <button
                    key={img}
                    className={`sidebar-btn ${selectedFile === img ? 'active' : ''}`}
                    onClick={() => onSelectFile(img)}
                  >
                    🖼️ {img.split('/').pop()}
                  </button>
                ))}
              </div>
            </details>
          )}

          {python_scripts.length > 0 && (
            <details className="sidebar-expander">
              <summary>🐍 Python ({python_scripts.length})</summary>
              <div className="sidebar-expander-content">
                {python_scripts.map((s) => (
                  <button
                    key={s}
                    className={`sidebar-btn ${selectedFile === s ? 'active' : ''}`}
                    onClick={() => onSelectFile(s)}
                  >
                    🐍 {s.split('/').pop()}
                  </button>
                ))}
              </div>
            </details>
          )}

          {output_files.length > 0 && (
            <details className="sidebar-expander">
              <summary>📄 All Files ({output_files.length})</summary>
              <div className="sidebar-expander-content">
                {output_files.length > 60 && (
                  <div style={{ fontSize: '11px', color: 'rgba(255,255,255,0.4)', padding: '4px 12px' }}>
                    Showing first 60 of {output_files.length} files
                  </div>
                )}
                {output_files.slice(0, 60).map((fp) => {
                  const name = runDir ? fp.replace(runDir + '/', '') : fp.split('/').pop();
                  return (
                    <button
                      key={fp}
                      className={`sidebar-btn ${selectedFile === fp ? 'active' : ''}`}
                      onClick={() => onSelectFile(fp)}
                    >
                      {fileIcon(fp)} {name}
                    </button>
                  );
                })}
              </div>
            </details>
          )}
        </div>
      )}
    </aside>
  );
}
