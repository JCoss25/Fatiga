/* Utilidades compartidas del frontend. */
const API = "/api";

async function api(path, { method = "GET", body, token } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers["X-Admin-Token"] = token;
  const res = await fetch(API + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try { data = await res.json(); } catch (_) {}
  if (!res.ok) {
    const msg = (data && (data.detail || data.message)) || `Error ${res.status}`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

const SEMAFORO = {
  VERDE:    { bg: "bg-emerald-100", text: "text-emerald-700", ring: "ring-emerald-300", dot: "bg-emerald-500", label: "Verde" },
  AMARILLO: { bg: "bg-amber-100",   text: "text-amber-800",   ring: "ring-amber-300",   dot: "bg-amber-500",   label: "Amarillo" },
  ROJO:     { bg: "bg-red-100",     text: "text-red-700",     ring: "ring-red-300",     dot: "bg-red-500",     label: "Rojo" },
};

function badgeSemaforo(sem) {
  const s = SEMAFORO[sem] || SEMAFORO.VERDE;
  return `<span class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${s.bg} ${s.text}">
    <span class="h-2 w-2 rounded-full ${s.dot}"></span>${s.label}</span>`;
}

function getToken() { return sessionStorage.getItem("fatiga_token") || ""; }
function setToken(t) { sessionStorage.setItem("fatiga_token", t); }
function clearToken() { sessionStorage.removeItem("fatiga_token"); }

function hoyISO() {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

function toast(msg, type = "info") {
  const colors = { info: "bg-slate-800", ok: "bg-emerald-600", error: "bg-red-600" };
  const el = document.createElement("div");
  el.className = `fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-lg px-5 py-3 text-sm font-medium text-white shadow-lg ${colors[type] || colors.info}`;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}
