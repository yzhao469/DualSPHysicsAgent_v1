import React, { useState } from 'react';
import { getImageUrl } from '../api';

export default function Visualization({ images }) {
  const [selected, setSelected] = useState(0);

  if (!images || images.length === 0) {
    return (
      <div className="empty-state">
        <div className="icon">🖼️</div>
        <p>No visualizations available yet.</p>
      </div>
    );
  }

  const imgPath = images[selected] || images[0];
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
          <img src={getImageUrl(imgPath)} alt={name} />
          <div className="viz-caption">{name}</div>
        </div>
      </div>
    </div>
  );
}
