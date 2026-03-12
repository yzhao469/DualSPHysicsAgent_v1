import React, { useState, useEffect } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { fetchFileContent, saveFile, getDownloadUrl } from '../api';

export default function ScriptEditor({ scriptPath, onSaved }) {
  const [content, setContent] = useState('');
  const [editMode, setEditMode] = useState(false);
  const [edited, setEdited] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!scriptPath) return;
    setLoading(true);
    fetchFileContent(scriptPath)
      .then((data) => {
        if (data.type === 'text') {
          setContent(data.content);
          setEdited(data.content);
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [scriptPath]);

  if (!scriptPath) {
    return (
      <div className="empty-state">
        <div className="icon">📜</div>
        <p>No post-processing script available yet.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="empty-state">
        <div className="icon">⏳</div>
        <p>Loading file…</p>
      </div>
    );
  }

  const handleSave = async () => {
    try {
      await saveFile(scriptPath, edited);
      setContent(edited);
      setEditMode(false);
      onSaved?.();
    } catch (err) {
      console.error('Save failed:', err);
    }
  };

  return (
    <div className="editor-panel">
      <div className="editor-toolbar">
        <label className="toggle-label">
          <input
            type="checkbox"
            checked={editMode}
            onChange={(e) => {
              setEditMode(e.target.checked);
              if (e.target.checked) setEdited(content);
            }}
          />
          ✏️ Edit
        </label>
        <div style={{ flex: 1 }} />
        {editMode && (
          <button className="btn btn-primary" onClick={handleSave}>
            💾 Save Changes
          </button>
        )}
        <a className="btn" href={getDownloadUrl(scriptPath)} download>
          ⬇️ Download
        </a>
      </div>

      <div className="editor-area">
        {editMode ? (
          <textarea
            className="editor-textarea"
            value={edited}
            onChange={(e) => setEdited(e.target.value)}
            spellCheck={false}
          />
        ) : (
          <SyntaxHighlighter
            language="bash"
            style={oneLight}
            showLineNumbers
            customStyle={{ borderRadius: '8px', fontSize: '13px' }}
          >
            {content}
          </SyntaxHighlighter>
        )}
      </div>
    </div>
  );
}
