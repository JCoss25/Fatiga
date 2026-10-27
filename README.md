# Fatiga, Seguridad y Comercial

Aplicación web que integra:

- el **Test diario de alertamiento por fatiga laboral** (10 preguntas, puntaje 0–20,
  semáforo Verde/Amarillo/Rojo, reglas de pregunta crítica y jornada extra),
- el **Check List de Seguridad REG-SST-25**,
- el **Panel de reportes** de fatiga y seguridad,
- el módulo **Comercial** de cotización de daños (Orden de Reparación TOT).

Los datos de fatiga/seguridad viven en la base MySQL de AWS (`kogn1v1s`, Amazon RDS).
El módulo Comercial usa las mismas credenciales en producción (tablas `cot_*`) y
SQLite local para pruebas.

---

## ¿Qué incluye?

- **Kiosco** (`/kiosco.html`): el trabajador se identifica (se busca en la tabla
  `usuarios` existente o captura manual) y responde el test. El puntaje, el
  semáforo y la recomendación se calculan **en vivo** y al guardar.
- **Panel de supervisor** (`/panel.html`): protegido por clave. Muestra el
  resumen del día, filtros (fecha, semáforo, turno, departamento, búsqueda),
  detalle por pregunta, historial por trabajador, alerta de **patrón repetido**
  y exportación a CSV.
- **Comercial** (`/comercial/`): solicitud de cotización de daños (Orden de
  Reparación TOT), aprobación con número de SB, comentarios, adjuntos,
  recordatorios cada 2 días, PDF e indicadores. Tiene dos accesos:
  **Solicitante** y **Aprobador**.
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

## Módulo Comercial (Cotización de daños)

Se entra desde el portal principal → tarjeta **Comercial**. Dentro hay dos módulos:

| Acceso | Clave inicial | Función |
|---|---|---|
| Solicitante | `Soli.2026` | Crea la Orden de Reparación TOT, adjunta cotizaciones y la envía. |
| Aprobador | `Apro.2026` | Revisa, comenta, aprueba con número de SB o rechaza. |

Flujo:

1. El solicitante crea la solicitud. El **folio es automático con consecutivo
   global** (`TOT-LC-0001`, `TOT-NDVC-0002`, `TOT-LC-0003`…).
2. Al enviarla se manda correo al aprobador.
3. Si sigue **PENDIENTE 2 días**, se envía un recordatorio y se repite cada 48 h.
4. El aprobador puede **aprobar con número de SB** o **rechazar con motivo**.
5. El solicitante recibe el resultado y puede **generar el PDF**.
6. El aprobador cuenta con **indicadores** (pendientes, vencidas, tiempo promedio,
   efectividad, recordatorios y volumen por mes).

### Base local vs producción

- Este equipo usa `COT_DATABASE_URL=sqlite:///./comercial_local.db` en `.env`
  para que el módulo funcione sin RDS. La base se crea con:
  `python db/migrate_comercial.py`.
- Para producción (misma base `kogn1v1s`), elimina `COT_DATABASE_URL` del `.env`
  y ejecuta `python db/migrate_comercial.py` (crea las tablas `cot_*` con el
  usuario admin).
- Para borrar todas las solicitudes/comentarios/adjuntos/correos conservando los
  catálogos: `python db/reset_comercial.py`.

### Correo con Gmail (cuentas exclusivas)

En `.env`:

```ini
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_TLS=starttls
SMTP_USER=cuenta.notificaciones@gmail.com
SMTP_PASSWORD=contraseña_de_aplicacion_de_16_caracteres
SMTP_FROM=cuenta.notificaciones@gmail.com
SMTP_FROM_NAME=Kogn1v1s - Comercial
CORREO_SIMULADO=0
APP_URL=http://127.0.0.1:8010
SOLICITANTE_EMAIL=cuenta.solicitante@gmail.com
APROBADOR_EMAIL=cuenta.aprobador@gmail.com
```

Para Gmail hay que activar **verificación en 2 pasos** y generar una
**contraseña de aplicación** (no sirve la contraseña normal). Mientras
`CORREO_SIMULADO=1`, los correos se guardan en la bandeja interna del aprobador
y se imprimen en consola.

## Estructura

```
app-fatiga/
├── backend/            API FastAPI
│   ├── main.py         rutas/endpoints (incluye el módulo Comercial)
│   ├── models.py       tablas (usuarios existente + fatiga_*)
│   ├── schemas.py      validación de datos
│   ├── scoring.py      reglas de puntaje/semáforo/jornada extra
│   ├── db.py           conexión MySQL/RDS + Secrets Manager
│   └── comercial/      módulo Comercial (cot_*)
│       ├── router.py   API /api/comercial
│       ├── models.py   solicitudes, comentarios, adjuntos, correos, catálogos
│       ├── schemas.py  validación Pydantic
│       ├── auth.py     claves Solicitante / Aprobador
│       ├── correo.py   SMTP Gmail + modo simulado
│       └── db.py       engine propio (SQLite local o MySQL/RDS)
├── frontend/           interfaz (HTML + Tailwind + JS, sin build)
│   └── comercial/      portal, solicitante, aprobador y PDF
├── db/
│   ├── schema.sql              tablas del test de fatiga/SST
│   ├── migrate.py              aplica schema.sql
│   ├── comercial_schema.sql    tablas cot_* para MySQL
│   ├── migrate_comercial.py    crea tablas (SQLite o MySQL)
│   └── reset_comercial.py      borra solicitudes/comentarios/adjuntos/correos
├── deploy/             Dockerfile + guía AWS (AWS_DEPLOY.md)
├── requirements.txt
├── docker-compose.yml
└── run_local.ps1       arranque en Windows
```

## Tablas nuevas en la BD

- `fatiga_preguntas` — catálogo de las 10 preguntas.
- `fatiga_tests` — encabezado de cada test (puntaje, semáforo, jornada extra…).
- `fatiga_respuestas` — valor 0/1/2 por pregunta.

Módulo Comercial (prefijo `cot_`):

- `cot_solicitudes` — Orden de Reparación TOT.
- `cot_comentarios` — comentarios, revisiones, aprobación/rechazo y bitácora.
- `cot_adjuntos` — archivos de cotización.
- `cot_correos` — bitácora/bandeja de correos.
- `cot_catalogos` — clientes, ubicaciones, tipos de servicio, números de parte y proveedores.

En local se crean en `comercial_local.db` (SQLite); en AWS, en `kogn1v1s` (MySQL).
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

### Módulo Comercial en local

El portal incluye la tarjeta **Comercial** con dos accesos:

- Solicitante: `Soli.2026`
- Aprobador: `Apro.2026`

La base local del módulo (`comercial_local.db`) se crea con:

```bash
python db/migrate_comercial.py
```

Para borrar todas las solicitudes, comentarios, adjuntos y correos (conservando
catálogos):

```bash
python db/reset_comercial.py
```

Si la red no tiene acceso a RDS, el módulo Comercial sigue funcionando con
SQLite local; el kiosco y el panel de fatiga sí requieren la base de AWS.

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
- Cambiar también `SOLICITANTE_PASSWORD` (`Soli.2026`) y `APROBADOR_PASSWORD`
  (`Apro.2026`) del módulo Comercial antes de publicarlo.
- Para Gmail usa una **contraseña de aplicación**, no la contraseña normal de la
  cuenta; guárdala en Secrets Manager y no la escribas en el repositorio.
- `.env` no se sube al repo; `.server.pid` tampoco.
- Checklist completo en `deploy/AWS_DEPLOY.md`.
