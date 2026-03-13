import React, { useState, useEffect } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { fetchFileContent, saveFile, getDownloadUrl } from '../api';

export default function ScriptEditor({ scriptPath, onSaved, onError }) {
  const [content, setContent] = useState('');
  const [editMode, setEditMode] = useState(false);
  const [edited, setEdited] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!scriptPath) return;
    let cancelled = false;
    setLoading(true);
    fetchFileContent(scriptPath)
      .then((data) => {
        if (!cancelled && data.type === 'text') {
          setContent(data.content);
          setEdited(data.content);
        }
      })
      .catch((err) => { if (!cancelled) console.error(err); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [scriptPath]);

  if (!scriptPath) {
    return (
      <div className="empty-state">
        <p>No post-processing script available yet.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="empty-state">
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
      onError?.(err.message || 'Failed to save file');
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
          Edit
        </label>
        <div style={{ flex: 1 }} />
        {editMode && (
          <button className="btn btn-primary" onClick={handleSave}>
            Save
          </button>
        )}
        <a className="btn" href={getDownloadUrl(scriptPath)} download>
          Download
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
            style={oneDark}
            showLineNumbers
            customStyle={{ borderRadius: '5px', fontSize: '12px', border: '1px solid rgba(255,255,255,0.06)' }}
          >
            {content}
          </SyntaxHighlighter>
        )}
      </div>
    </div>
  );
}
