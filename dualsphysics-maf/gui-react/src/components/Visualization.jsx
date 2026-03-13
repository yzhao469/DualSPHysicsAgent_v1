import React, { useState, useEffect } from 'react';
import { getImageUrl } from '../api';

export default function Visualization({ images }) {
  const [selected, setSelected] = useState(0);
  const [imgError, setImgError] = useState(false);

  // Reset selection when images list changes
  useEffect(() => {
    setSelected(0);
    setImgError(false);
  }, [images]);

  if (!images || images.length === 0) {
    return (
      <div className="empty-state">
        <div className="icon">🖼️</div>
        <p>No visualizations available yet.</p>
      </div>
    );
  }

  const safeIndex = selected < images.length ? selected : 0;
  const imgPath = images[safeIndex];
  const name = imgPath.split('/').pop();

  return (
    <div className="viz-panel">
      {images.length > 1 && (
        <select
          className="viz-select"
          value={selected}
          onChange={(e) => setSelected(Number(e.target.value))}
        >
          {images.map((img, i) => (
            <option key={img} value={i}>
              {img.split('/').pop()}
            </option>
          ))}
        </select>
      )}

      <div className="viz-image">
        <div>
          {imgError ? (
            <p style={{ color: '#ef4444' }}>Failed to load image: {name}</p>
          ) : (
            <img
              src={getImageUrl(imgPath)}
              alt={name}
              onError={() => setImgError(true)}
            />
          )}
          <div className="viz-caption">{name}</div>
        </div>
      </div>
    </div>
  );
}
