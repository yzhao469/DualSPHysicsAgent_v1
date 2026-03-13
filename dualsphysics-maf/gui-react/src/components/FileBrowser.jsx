import React from 'react';
import FilePreview from './FilePreview';

function fileExt(path) {
  return path.split('.').pop().toLowerCase();
}

export default function FileBrowser({ files, runDir, selectedFile, onSelectFile }) {
  if (!files || files.length === 0) {
    return (
      <div className="empty-state">
        <p>No output files generated yet.</p>
      </div>
    );
  }

  // Group by sub-directory
  const grouped = {};
  for (const fp of files) {
    const rel = runDir ? fp.replace(runDir + '/', '') : fp;
    const dir = rel.includes('/') ? rel.substring(0, rel.lastIndexOf('/')) : 'root';
    if (!grouped[dir]) grouped[dir] = [];
    grouped[dir].push(fp);
  }

  return (
    <div className="file-browser">
      {Object.entries(grouped)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([dir, dirFiles]) => (
          <div key={dir} className="file-group">
            <details open>
              <summary>
                {dir}/ ({dirFiles.length})
              </summary>
              <div className="file-group-items">
                {dirFiles.map((fp) => (
                  <button
                    key={fp}
                    className="file-item-btn"
                    onClick={() => onSelectFile(fp)}
                  >
                    <span className="file-ext" style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: '10px',
                      color: 'var(--text-tertiary)',
                      textTransform: 'uppercase',
                      minWidth: '28px',
                    }}>
                      {fileExt(fp)}
                    </span>
                    {fp.split('/').pop()}
                  </button>
                ))}
              </div>
            </details>
          </div>
        ))}

      {/* Inline preview */}
      {selectedFile && (
        <div className="file-preview-overlay">
          <div className="file-preview-header">
            <h4>{selectedFile.split('/').pop()}</h4>
            <button className="btn" onClick={() => onSelectFile(null)}>
              Close
            </button>
          </div>
          <div className="file-preview-body">
            <FilePreview path={selectedFile} />
          </div>
        </div>
      )}
    </div>
  );
}
