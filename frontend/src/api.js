const BASE = import.meta.env.VITE_API_URL || "";

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

async function get(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

export const api = {
  startStream: (query) =>
    new EventSource(`${BASE}/api/chat/start/stream?query=${encodeURIComponent(query)}`),

  selectStream: (threadId, indices, action = "approve") =>
    new EventSource(
      `${BASE}/api/chat/select/stream?thread_id=${threadId}&selected_indices=${indices}&action=${action}`
    ),

  reject:       (body) => post("/api/chat/reject",   body),
  addBookmark:  (body) => post("/api/chat/bookmark",  body),
  getBookmarks: ()     => get("/api/chat/bookmarks"),
  createShare:  (body) => post("/api/chat/share",     body),
  getShare:     (code) => get(`/api/chat/share/${code}`),
};
