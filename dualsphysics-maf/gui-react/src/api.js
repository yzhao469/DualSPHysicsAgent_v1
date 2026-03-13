/**
 * API client for communicating with the FastAPI backend.
 */

const API_BASE = '/api';

/**
 * Fetch current session state.
 */
export async function fetchState() {
  const res = await fetch(`${API_BASE}/state`);
  if (!res.ok) throw new Error(`Failed to fetch state: ${res.status}`);
  return res.json();
}

/**
 * Start a new workflow with the given scenario.
 */
export async function startWorkflow(scenario) {
  const res = await fetch(`${API_BASE}/workflow/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scenario }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || `Failed to start workflow: ${res.status}`);
  }
  return res.json();
}

/**
 * Send a response to a pending HITL request.
 */
export async function respondToWorkflow(message) {
  const res = await fetch(`${API_BASE}/workflow/respond`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || `Failed to respond: ${res.status}`);
  }
  return res.json();
}

/**
 * Reset the workflow session.
 */
export async function resetWorkflow() {
  const res = await fetch(`${API_BASE}/workflow/reset`, {
    method: 'POST',
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || `Failed to reset: ${res.status}`);
  }
  return res.json();
}

/**
 * Fetch text content of a file.
 */
export async function fetchFileContent(path) {
  const res = await fetch(`${API_BASE}/files/content?path=${encodeURIComponent(path)}`);
  if (!res.ok) throw new Error(`Failed to fetch file: ${res.status}`);
  const contentType = res.headers.get('content-type') || '';
  if (contentType.startsWith('image/')) {
    const blob = await res.blob();
    return { type: 'image', url: URL.createObjectURL(blob), name: path.split('/').pop() };
  }
  return res.json();
}

/**
 * Save file content.
 */
export async function saveFile(path, content) {
  const res = await fetch(`${API_BASE}/files/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, content }),
  });
  if (!res.ok) throw new Error(`Failed to save file: ${res.status}`);
  return res.json();
}

/**
 * Get download URL for a file.
 */
export function getDownloadUrl(path) {
  return `${API_BASE}/files/download?path=${encodeURIComponent(path)}`;
}

/**
 * Get image URL for a file.
 */
export function getImageUrl(path) {
  return `${API_BASE}/files/image?path=${encodeURIComponent(path)}`;
}

/**
 * Create a WebSocket connection for real-time events.
 * Returns an object with { close, ws }.
 *
 * @param {Function} onMessage - Called with parsed event data
 * @param {Function} [onOpen] - Called when connection opens
 * @param {Function} [onClose] - Called when connection closes (for reconnect logic)
 */
export function createEventSocket(onMessage, onOpen, onClose) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws`;
  const ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    onOpen?.();
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.event && data.event.type !== 'heartbeat') {
        onMessage(data);
      }
    } catch {
      // ignore parse errors
    }
  };

  ws.onerror = (err) => {
    console.error('WebSocket error:', err);
  };

  ws.onclose = () => {
    onClose?.();
  };

  return {
    close: () => ws.close(),
    ws,
  };
}
