import React, { useState, useEffect } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { fetchFileContent, getImageUrl } from '../api';

export default function FilePreview({ path }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!path) return;
    let cancelled = false;
    setLoading(true);
    setData(null);

    const ext = path.split('.').pop().toLowerCase();
    if (['png', 'jpg', 'jpeg'].includes(ext)) {
      setData({ type: 'image', url: getImageUrl(path), name: path.split('/').pop() });
      setLoading(false);
      return;
    }

    fetchFileContent(path)
      .then((result) => { if (!cancelled) setData(result); })
      .catch((err) => {
        if (!cancelled) setData({ type: 'error', message: err.message });
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [path]);

  if (loading) return <p style={{ color: '#64748b' }}>Loading…</p>;
  if (!data) return <p style={{ color: '#64748b' }}>No preview available.</p>;

  if (data.type === 'image') {
    return <img src={data.url} alt={data.name || 'Preview'} style={{ maxWidth: '100%' }} />;
  }

  if (data.type === 'binary') {
    return (
      <p style={{ color: '#64748b' }}>
        Binary file — {data.size?.toLocaleString()} bytes
      </p>
    );
  }

  if (data.type === 'text') {
    // CSV: render as a simple table
    if (data.language === 'csv') {
      const lines = data.content.split('\n').filter(Boolean);
      if (lines.length > 0) {
        const delimiter = data.content.includes(';') ? ';' : ',';
        const header = lines[0].split(delimiter);
        const rows = lines.slice(1, 201).map((l) => l.split(delimiter));
        return (
          <table>
            <thead>
              <tr>
                {header.map((h, i) => (
                  <th key={i}>{h.trim()}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, ri) => (
                <tr key={ri}>
                  {row.map((cell, ci) => (
                    <td key={ci}>{cell.trim()}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        );
      }
    }

    // Code: syntax highlighted
    const lang = data.language && data.language !== 'text' ? data.language : undefined;
    if (lang) {
      return (
        <SyntaxHighlighter
          language={lang}
          style={oneLight}
          showLineNumbers
          customStyle={{ borderRadius: '8px', fontSize: '13px', margin: 0 }}
        >
          {data.content}
        </SyntaxHighlighter>
      );
    }

    // Plain text
    return (
      <pre className="code-block">{data.content}</pre>
    );
  }

  if (data.type === 'error') {
    return <p style={{ color: '#ef4444' }}>Error: {data.message}</p>;
  }

  return <p style={{ color: '#64748b' }}>No preview available.</p>;
}
