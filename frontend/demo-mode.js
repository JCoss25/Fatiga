/* Modo demo para revisar el modelo sin base de datos.
   Solo actúa si la URL lleva ?demo=1. No se despliega en AWS. */
(() => {
  if (!new URLSearchParams(location.search).has("demo")) return;
  const D = window.__DEMO__;
  if (!D) return;

  // El panel abre directamente como administrador para poder revisar
  // los catalogos y los indicadores.
  if (location.pathname.endsWith("/panel.html") || location.pathname.endsWith("panel.html")) {
    sessionStorage.setItem("fatiga_token", "demo");
    sessionStorage.setItem("fatiga_role", "admin");
  }

  const native = window.fetch.bind(window);
  const json = (data) => new Response(JSON.stringify(data), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });

  // Catalogos: persisten en localStorage para que el formulario de SST
  // vea lo que se agrego desde el panel (aunque sea otra pagina).
  const CAT_KEY = "demo_catalogos_v2";
  const catalogs = () => {
    try {
      const raw = localStorage.getItem(CAT_KEY);
      if (raw) return JSON.parse(raw);
    } catch (_) {}
    const base = JSON.parse(JSON.stringify(D.catalogos || { auditores: [], areas: [] }));
    localStorage.setItem(CAT_KEY, JSON.stringify(base));
    return base;
  };
  const saveCatalogs = (c) => localStorage.setItem(CAT_KEY, JSON.stringify(c));

  window.fetch = (input, init = {}) => {
    const u = String(typeof input === "string" ? input : input.url);
    const method = String(init.method || "GET").toUpperCase();

    let body = {};
    try { body = JSON.parse(init.body || "{}"); } catch (_) {}

    if (u.includes("indicadores/fatiga")) {
      const qs = new URLSearchParams(u.split("?")[1] || "");
      return json({ ...D.indicadores.fatiga, desde: qs.get("desde") || D.indicadores.fatiga.desde, hasta: qs.get("hasta") || D.indicadores.fatiga.hasta });
    }
    if (u.includes("indicadores/sst")) {
      const qs = new URLSearchParams(u.split("?")[1] || "");
      return json({ ...D.indicadores.sst, desde: qs.get("desde") || D.indicadores.sst.desde, hasta: qs.get("hasta") || D.indicadores.sst.hasta });
    }

    if (u.includes("sst/catalogos")) return json(catalogs());

    const postCat = u.match(/sst\/(auditores|areas)$/);
    if (postCat && method === "POST") {
      const key = postCat[1];
      const c = catalogs();
      const nombre = String(body.nombre || "").trim();
      if (!nombre) return new Response(JSON.stringify({ detail: "Escribe un nombre." }), { status: 422, headers: { "Content-Type": "application/json" } });
      const existing = c[key].find((x) => x.nombre.toLowerCase() === nombre.toLowerCase());
      if (existing) return json(existing);
      const item = { id: Date.now(), nombre };
      c[key].push(item);
      c[key].sort((a, b) => a.nombre.localeCompare(b.nombre));
      saveCatalogs(c);
      return json(item);
    }

    const delCat = u.match(/sst\/(auditores|areas)\/(\d+)/);
    if (delCat && method === "DELETE") {
      const key = delCat[1];
      const id = Number(delCat[2]);
      const c = catalogs();
      c[key] = c[key].filter((x) => Number(x.id) !== id);
      saveCatalogs(c);
      return json({ ok: true });
    }

    if (u.includes("sst/preguntas")) return json(D.preguntas);
    if (u.includes("sst/resumen")) return json(D.resumen);
    if (/sst\/\d+/.test(u)) return json(D.detalle);
    if (u.includes("sst") && method === "POST") {
      const seguras = (body.respuestas || []).filter((r) => r.estado === "SEGURO").length;
      return json({
        ok: true,
        id_auditoria: 999,
        seguras,
        inseguras: 18 - seguras,
        porcentaje: Math.round((seguras / 18) * 100),
      });
    }
    if (u.includes("sst")) return json(D.lista);
    if (u.includes("login")) return json({ ok: true, role: "admin" });
    if (/empleados\/\d+\/historial/.test(u)) return json(D.fatigaTests);
    if (u.includes("empleados")) return json(D.empleados || []);
    if (/tests\/\d+/.test(u)) return json(D.fatigaDetalle);
    if (u.includes("tests")) return json(D.fatigaTests);
    if (u.includes("resumen")) return json(D.fatigaResumen);
    return native(input, init);
  };

  document.addEventListener("DOMContentLoaded", () => {
    const bar = document.createElement("div");
    bar.textContent = "MODO DEMO · datos de ejemplo · catálogos en este navegador · solo para revisión";
    bar.style.cssText =
      "background:#0b2545;color:#e9edf3;text-align:center;font:600 11px/1.4 system-ui;padding:6px 10px;letter-spacing:.02em;position:relative;z-index:80";
    document.body.prepend(bar);
  });
})();
