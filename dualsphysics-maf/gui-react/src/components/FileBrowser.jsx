import React from 'react';
import FilePreview from './FilePreview';

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

export default function FileBrowser({ files, runDir, selectedFile, onSelectFile }) {
  if (!files || files.length === 0) {
    return (
      <div className="empty-state">
        <div className="icon">📁</div>
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
                📂 {dir} ({dirFiles.length} files)
              </summary>
              <div className="file-group-items">
                {dirFiles.map((fp) => (
                  <button
                    key={fp}
                    className="file-item-btn"
                    onClick={() => onSelectFile(fp)}
                  >
                    {fileIcon(fp)} {fp.split('/').pop()}
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
            <h4>Viewing: {selectedFile.split('/').pop()}</h4>
            <button className="btn" onClick={() => onSelectFile(null)}>
              ✕ Close
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
