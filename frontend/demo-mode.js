/* Modo demo para revisar el modelo sin base de datos.
   Solo actúa si la URL lleva ?demo=1. No se despliega en AWS. */
(() => {
  if (!new URLSearchParams(location.search).has("demo")) return;
  const D = window.__DEMO__;
  if (!D) return;

  // El panel abre directamente como revisor.
  if (location.pathname.endsWith("/panel.html") || location.pathname.endsWith("panel.html")) {
    sessionStorage.setItem("fatiga_token", "demo");
    sessionStorage.setItem("fatiga_role", "revisor");
  }

  const native = window.fetch.bind(window);
  const json = (data) => new Response(JSON.stringify(data), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });

  window.fetch = (input, init = {}) => {
    const u = String(typeof input === "string" ? input : input.url);
    const method = String(init.method || "GET").toUpperCase();

    if (u.includes("sst/preguntas")) return json(D.preguntas);
    if (u.includes("sst/resumen")) return json(D.resumen);
    if (/sst\/\d+/.test(u)) return json(D.detalle);
    if (u.includes("sst") && method === "POST") {
      let body = {};
      try { body = JSON.parse(init.body || "{}"); } catch (_) {}
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
    if (u.includes("login")) return json({ ok: true, role: "revisor" });
    if (/empleados\/\d+\/historial/.test(u)) return json(D.fatigaTests);
    if (u.includes("empleados")) return json(D.empleados || []);
    if (/tests\/\d+/.test(u)) return json(D.fatigaDetalle);
    if (u.includes("tests")) return json(D.fatigaTests);
    if (u.includes("resumen")) return json(D.fatigaResumen);
    return native(input, init);
  };

  document.addEventListener("DOMContentLoaded", () => {
    const bar = document.createElement("div");
    bar.textContent = "MODO DEMO · datos de ejemplo · no guarda nada · solo para revisión";
    bar.style.cssText =
      "background:#0b2545;color:#e9edf3;text-align:center;font:600 11px/1.4 system-ui;padding:6px 10px;letter-spacing:.02em;position:relative;z-index:80";
    document.body.prepend(bar);
  });
})();
