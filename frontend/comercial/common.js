/* Utilidades compartidas del módulo Comercial (Cotización de daños). */
const API = "../api/comercial";

async function api(path, { method = "GET", body, token, blob = false } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers["X-Cot-Token"] = token;
  const res = await fetch(API + path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let data = null;
    try { data = await res.json(); } catch (_) {}
    const raw = data && (data.detail || data.message);
    const msg = typeof raw === "string" ? raw : raw ? JSON.stringify(raw) : `Error ${res.status}`;
    throw new Error(msg);
  }
  if (blob) return res.blob();
  try { return await res.json(); } catch (_) { return null; }
}

/* ------------------------------------------------------------------ */
/* Sesión                                                              */
/* ------------------------------------------------------------------ */
const SES = {
  token: () => sessionStorage.getItem("cot_token") || "",
  role: () => sessionStorage.getItem("cot_role") || "",
  nombre: () => sessionStorage.getItem("cot_nombre") || "",
  email: () => sessionStorage.getItem("cot_email") || "",
  set(r) {
    sessionStorage.setItem("cot_token", r.token || "");
    sessionStorage.setItem("cot_role", r.role || "");
    sessionStorage.setItem("cot_nombre", r.nombre || "");
    sessionStorage.setItem("cot_email", r.email || "");
  },
  clear() {
    ["cot_token", "cot_role", "cot_nombre", "cot_email"].forEach(k => sessionStorage.removeItem(k));
  },
};

async function entrar(password, roleRequerido) {
  const r = await api("/login", { method: "POST", token: password });
  if (roleRequerido && r.role !== roleRequerido) {
    throw new Error("Esa clave es de otro rol. Usa la clave correcta.");
  }
  SES.set({ ...r, token: password });
  return r;
}

async function validarSesion(roleRequerido) {
  const token = SES.token();
  if (!token || SES.role() !== roleRequerido) return null;
  try {
    const r = await api("/login", { method: "POST", token });
    if (r.role !== roleRequerido) throw new Error("rol distinto");
    SES.set({ ...r, token });
    return r;
  } catch (_) {
    SES.clear();
    return null;
  }
}

/* ------------------------------------------------------------------ */
/* Formato                                                             */
/* ------------------------------------------------------------------ */
const ESTATUS = {
  BORRADOR:  { label: "Borrador",  clase: "bg-slate-100 text-slate-600 ring-slate-200",   punto: "bg-slate-400" },
  PENDIENTE: { label: "Pendiente", clase: "bg-amber-100 text-amber-800 ring-amber-200",   punto: "bg-amber-500" },
  APROBADA:  { label: "Aprobada",  clase: "bg-emerald-100 text-emerald-700 ring-emerald-200", punto: "bg-emerald-500" },
  COMPRADO:  { label: "Comprado",  clase: "bg-sky-100 text-sky-700 ring-sky-200",         punto: "bg-sky-500" },
  CERRADO:   { label: "Cerrado",   clase: "bg-slate-800 text-slate-100 ring-slate-700",   punto: "bg-emerald-400" },
  RECHAZADA: { label: "Rechazada", clase: "bg-red-100 text-red-700 ring-red-200",         punto: "bg-red-500" },
  CANCELADA: { label: "Cancelada", clase: "bg-slate-100 text-slate-500 ring-slate-200",   punto: "bg-slate-400" },
};

function badgeEstatus(estatus) {
  const e = ESTATUS[estatus] || ESTATUS.BORRADOR;
  return `<span class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ${e.clase}">
    <span class="h-1.5 w-1.5 rounded-full ${e.punto}"></span>${e.label}</span>`;
}

function money(valor, moneda = "MXN") {
  const n = Number(valor || 0);
  try {
    return new Intl.NumberFormat("es-MX", {
      style: "currency", currency: moneda || "MXN", minimumFractionDigits: 2,
    }).format(n);
  } catch (_) {
    return `$${n.toFixed(2)} ${moneda || ""}`;
  }
}

function fecha(iso) {
  if (!iso) return "—";
  const d = new Date(iso.length <= 10 ? iso + "T12:00:00" : iso);
  if (isNaN(d)) return iso;
  return new Intl.DateTimeFormat("es-MX", { day: "2-digit", month: "short", year: "numeric" }).format(d);
}

function fechaHora(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return new Intl.DateTimeFormat("es-MX", {
    day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  }).format(d);
}

function diasTexto(n) {
  const d = Number(n || 0);
  return d === 0 ? "hoy" : d === 1 ? "1 día" : `${d} días`;
}

function escapeHtml(v) {
  return String(v ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function formatoBytes(n) {
  const b = Number(n || 0);
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(0)} KB`;
  return `${(b / (1024 * 1024)).toFixed(1)} MB`;
}

function toast(msg, type = "info") {
  const colors = { info: "bg-slate-800", ok: "bg-emerald-600", error: "bg-red-600" };
  const el = document.createElement("div");
  el.className = `fixed bottom-6 left-1/2 z-[80] -translate-x-1/2 rounded-lg px-5 py-3 text-sm font-medium text-white shadow-lg ${colors[type] || colors.info}`;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

/* ------------------------------------------------------------------ */
/* Catálogos                                                           */
/* ------------------------------------------------------------------ */
function llenarDatalist(id, items) {
  const dl = document.getElementById(id);
  if (!dl) return;
  dl.innerHTML = (items || []).map(i => `<option value="${escapeHtml(i.valor)}"></option>`).join("");
}

async function cargarCatalogos() {
  const data = await api("/catalogos", { token: SES.token() });
  llenarDatalist("dl-cliente", data.cliente);
  llenarDatalist("dl-ubicacion", data.ubicacion);
  llenarDatalist("dl-tipo_servicio", data.tipo_servicio);
  llenarDatalist("dl-no_parte", data.no_parte);
  llenarDatalist("dl-proveedor", data.proveedor);
  return data;
}

async function agregarCatalogo(tipo, valor, etiqueta) {
  const limpio = String(valor || "").trim();
  if (!limpio) return;
  await api("/catalogos", { method: "POST", token: SES.token(), body: { tipo, valor: limpio } });
  await cargarCatalogos();
  toast(`${etiqueta} agregado al catálogo`, "ok");
}

/* ------------------------------------------------------------------ */
/* Archivos / documento                                                */
/* ------------------------------------------------------------------ */
function leerArchivoBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const raw = String(reader.result || "");
      resolve(raw.includes(",") ? raw.slice(raw.indexOf(",") + 1) : raw);
    };
    reader.onerror = () => reject(new Error("No se pudo leer el archivo"));
    reader.readAsDataURL(file);
  });
}

function abrirDocumento(id) {
  window.open(`documento.html?id=${encodeURIComponent(id)}`, "_blank");
}

async function descargarAdjunto(id, nombre) {
  const blob = await api(`/adjuntos/${id}`, { token: SES.token(), blob: true });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nombre || "cotizacion";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}
