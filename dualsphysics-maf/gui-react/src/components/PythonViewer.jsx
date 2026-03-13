import React, { useState, useEffect } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { fetchFileContent, getDownloadUrl } from '../api';

function PythonCard({ path }) {
  const [content, setContent] = useState(null);
  const [open, setOpen] = useState(true);
  const name = path.split('/').pop();

  useEffect(() => {
    fetchFileContent(path)
      .then((data) => {
        if (data.type === 'text') setContent(data.content);
      })
      .catch(console.error);
  }, [path]);

  return (
    <div className="python-card">
      <div className="python-card-header" onClick={() => setOpen(!open)}>
        <h4>🐍 {name}</h4>
        <a
          className="btn"
          href={getDownloadUrl(path)}
          download
          onClick={(e) => e.stopPropagation()}
        >
          ⬇️ Download
        </a>
      </div>
      {open && content !== null && (
        <div className="python-card-body">
          <SyntaxHighlighter
            language="python"
            style={oneLight}
            showLineNumbers
            customStyle={{ margin: 0, borderRadius: 0, fontSize: '13px' }}
          >
            {content}
          </SyntaxHighlighter>
        </div>
      )}
    </div>
  );
}

export default function PythonViewer({ scripts }) {
  if (!scripts || scripts.length === 0) {
    return (
      <div className="empty-state">
        <div className="icon">🐍</div>
        <p>
          No Python scripts generated yet. The agent creates analysis scripts
          during post-processing.
        </p>
      </div>
    );
  }

  return (
    <div className="python-cards">
      {scripts.map((s) => (
        <PythonCard key={s} path={s} />
      ))}
    </div>
  );
}
