# Test de Alertamiento por Fatiga Laboral

Aplicación web que digitaliza el **Test diario de alertamiento por fatiga laboral**
(10 preguntas, puntaje 0–20, semáforo Verde/Amarillo/Rojo, reglas de pregunta
crítica y jornada extra). Guarda los resultados en la base de datos MySQL de AWS
(`kogn1v1s`, Amazon RDS) y ofrece un panel de consulta para supervisores.

---

## ¿Qué incluye?

- **Kiosco** (`/kiosco.html`): el trabajador se identifica (se busca en la tabla
  `usuarios` existente o captura manual) y responde el test. El puntaje, el
  semáforo y la recomendación se calculan **en vivo** y al guardar.
- **Panel de supervisor** (`/panel.html`): protegido por clave. Muestra el
  resumen del día, filtros (fecha, semáforo, turno, departamento, búsqueda),
  detalle por pregunta, historial por trabajador, alerta de **patrón repetido**
  y exportación a CSV.
- **API REST** documentada automáticamente en `/docs`.

## Reglas implementadas (tomadas del documento)

| Semáforo | Puntaje | Jornada extra |
|---|---|---|
| 🟢 Verde | 0 – 5 | Puede (si el supervisor valida) |
| 🟡 Amarillo | 6 – 10 | No se recomienda |
| 🔴 Rojo | 11 – 20 | No debe exponerse |

- **Preguntas críticas ⚠** (1, 3, 8, 9 y 10): si alguna tiene **2 puntos**, el
  trabajador **no** debe hacer jornada extra **aunque el total sea verde**.
- Patrón repetido: 2 o más días en amarillo/rojo en la última semana.

## Estructura

```
app-fatiga/
├── backend/            API FastAPI
│   ├── main.py         rutas/endpoints
│   ├── models.py       tablas (usuarios existente + fatiga_*)
│   ├── schemas.py      validación de datos
│   ├── scoring.py      reglas de puntaje/semáforo/jornada extra
│   └── db.py           conexión MySQL/RDS + Secrets Manager
├── frontend/           interfaz (HTML + Tailwind + JS, sin build)
├── db/
│   ├── schema.sql      tablas nuevas del test
│   └── migrate.py      aplica schema.sql (usa credenciales admin)
├── deploy/             Dockerfile + guía AWS (AWS_DEPLOY.md)
├── requirements.txt
├── docker-compose.yml
└── run_local.ps1       arranque en Windows
```

## Tablas nuevas en la BD

- `fatiga_preguntas` — catálogo de las 10 preguntas.
- `fatiga_tests` — encabezado de cada test (puntaje, semáforo, jornada extra…).
- `fatiga_respuestas` — valor 0/1/2 por pregunta.

No se modifica ninguna tabla existente.

---

## Cómo correr en local (Windows)

> Tu sistema tiene la ejecución de scripts de PowerShell **bloqueada**, por eso
> se usan los lanzadores `.cmd` (que evitan el bloqueo automáticamente).

**Día a día (lo normal):** doble clic en **`start_server.cmd`**.
Levanta la app en segundo plano (no se cae al cerrar la ventana) y abre el
navegador en `http://127.0.0.1:8010`. Para apagarla: **`stop_server.cmd`**.

**Primera vez / tras cambiar dependencias:** doble clic en **`run_local.cmd`**
(crea el entorno virtual, instala dependencias y deja la app corriendo en esa
ventana; no la cierres mientras la uses).

### Equivalente en PowerShell

```powershell
.\start_server.cmd     # arrancar en segundo plano
.\stop_server.cmd      # detener
.\run_local.cmd        # primera vez (crea venv + instala)
```

### Manualmente

```powershell
python -m venv $env:USERPROFILE\.venvs\fatiga
& "$env:USERPROFILE\.venvs\fatiga\Scripts\python.exe" -m pip install -r requirements.txt
& "$env:USERPROFILE\.venvs\fatiga\Scripts\python.exe" -m uvicorn backend.main:app --port 8010 --reload
```

### Con Docker (si lo tienes instalado)

```bash
docker compose up --build
```

### Crear/actualizar tablas

```bash
python db/migrate.py
```

### Si la app abre pero el kiosco o el panel no cargan

1. Prueba `http://127.0.0.1:8010/api/ping`: debe responder `{"ok":true,"app":"fatiga"}` aunque la base esté caída.
2. Prueba `http://127.0.0.1:8010/api/health`:
   - `200` = base conectada.
   - `503` con `timed out` = tu red no está permitida en el **security group** de RDS, o la instancia está detenida. El SG solo acepta ciertas IPs; agrega tu IP actual como `/32` (temporal) o usa VPN/bastión.
3. El servidor local usa el puerto **8010** a propósito. El 8000 puede estar ocupado por otro proyecto (Kandy); no lo apagues desde aquí.
4. `start_server.ps1` busca `/api/ping`, no solo el puerto; así no confunde otra app con Fatiga.
5. `stop_server.ps1` lee `.server.pid` y verifica que el proceso sea `backend.main:app`; no mata otros proyectos.

---

## Subir a AWS

Toda la guía paso a paso está en **[`deploy/AWS_DEPLOY.md`](deploy/AWS_DEPLOY.md)**
(ECR + App Runner + VPC Connector + Secrets Manager). Resumen: se construye la
imagen con `deploy/Dockerfile` y se publica; el contenedor escucha en el puerto
`8000` y lee la contraseña de la BD desde **AWS Secrets Manager**.

---

## Seguridad

- El archivo `jcoss_accessKeys Fatiga.csv` del Escritorio contiene llaves AWS en
  texto plano. **Rótalas o retíralo** después de terminar la configuración; no
  debe quedarse ahí.
- El security group de RDS acepta solo IPs específicas; no lo abras a
  `0.0.0.0/0`. Para desarrollo, agrega tu IP actual como `/32` y retírala al
  terminar; para producción, usa VPN/bastión o el conector de VPC de App Runner.
- `DB_SSL` está en `disabled` en local. Antes de producción: `required`, rotar
  contraseñas, mover secretos a Secrets Manager y cambiar `ADMIN_PASSWORD`.
- `.env` no se sube al repo; `.server.pid` tampoco.
- Checklist completo en `deploy/AWS_DEPLOY.md`.
