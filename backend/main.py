"""API + servidor de la aplicacion de Fatiga, Seguridad y Comercial."""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import String, or_, select, text
from sqlalchemy.orm import Session

from . import scoring
from .auth import require_reports, role_for
from .comercial.db import SessionLocal as CotSessionLocal
from .comercial.router import procesar_recordatorios as procesar_recordatorios_comercial
from .comercial.router import router as comercial_router
from .db import get_db
from .models import FatigaFirma, FatigaPregunta, FatigaRespuesta, FatigaTest, Usuario
from .indicadores import router as indicadores_router
from .schemas import PreguntaOut, TestIn, TestOut
from .sst import router as sst_router

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
CLOUDFRONT_BASE = "https://dvctlemkfvc4i.cloudfront.net/"

log = logging.getLogger("comercial")


async def _loop_recordatorios_comercial():
    """Recordatorios de solicitudes Comercial pendientes (cada 30 min)."""
    await asyncio.sleep(20)
    intervalo = max(5, int(os.getenv("RECORDATORIOS_INTERVALO_MIN", "30")))
    while True:
        try:
            def run():
                db = CotSessionLocal()
                try:
                    return procesar_recordatorios_comercial(db)
                finally:
                    db.close()

            n = await asyncio.to_thread(run)
            if n:
                log.info("Recordatorios comercial enviados: %s", n)
        except Exception as e:  # noqa: BLE001
            log.warning("No se pudieron procesar recordatorios comercial: %s", str(e)[:300])
        await asyncio.sleep(intervalo * 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = None
    if os.getenv("RECORDATORIOS_ACTIVOS", "1").strip() == "1":
        task = asyncio.create_task(_loop_recordatorios_comercial())
    yield
    if task:
        task.cancel()


app = FastAPI(title="Kogn1v1s · Fatiga, Seguridad y Comercial", lifespan=lifespan)
app.include_router(sst_router)
app.include_router(indicadores_router)
app.include_router(comercial_router)


@app.middleware("http")
async def sin_cache_frontend(request, call_next):
    """Evita que el navegador muestre versiones viejas del HTML/JS en cache."""
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.endswith((".html", ".js", ".css")):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------
def decode_img(raw) -> Optional[str]:
    """img_empleado guarda la clave relativa como bytes (ej: 'empleados/1.jpeg')."""
    if raw is None:
        return None
    try:
        val = raw.decode("utf-8", "ignore") if isinstance(raw, (bytes, bytearray)) else str(raw)
    except Exception:
        return None
    val = val.strip()
    if not val:
        return None
    if val.startswith("http"):
        return val
    return CLOUDFRONT_BASE + val.lstrip("/")


def parse_time(value: Optional[str]):
    if not value:
        return None
    value = value.strip()
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    return None


# --------------------------------------------------------------------------
# Endpoints publicos
# --------------------------------------------------------------------------
@app.get("/api/ping")
def ping():
    """Latido sin base de datos, para que el arranque local no dependa de RDS."""
    return {"ok": True, "app": "fatiga"}


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    info = {"db": os.getenv("DB_NAME"), "host": os.getenv("DB_HOST")}
    try:
        db.execute(text("SELECT 1"))
        return {"ok": True, **info}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"ok": False, "error": str(e)[:300], **info},
        )


@app.get("/api/preguntas", response_model=List[PreguntaOut])
def preguntas(db: Session = Depends(get_db)):
    rows = db.scalars(select(FatigaPregunta).order_by(FatigaPregunta.orden)).all()
    return [
        PreguntaOut(
            id_pregunta=p.id_pregunta,
            seccion=p.seccion,
            orden=p.orden,
            texto=p.texto,
            critica=bool(p.critica),
            opciones=[p.opcion_0, p.opcion_1, p.opcion_2],
        )
        for p in rows
    ]


@app.post("/api/login")
def login(x_admin_token: Optional[str] = Header(default=None)):
    role = role_for(x_admin_token)
    if not role:
        raise HTTPException(status_code=401, detail="Clave de reportes incorrecta")
    return {"ok": True, "role": role}


@app.get("/api/empleados")
def empleados(q: str = Query(default="", max_length=80), db: Session = Depends(get_db)):
    """Busca empleados activos por nombre, No. de empleado, código, puesto,
    departamento o empresa. Devuelve las coincidencias conforme se encuentran."""
    stmt = select(Usuario).where(Usuario.estatus == 1)
    q = q.strip()
    if q:
        like = f"%{q}%"
        campos = [
            Usuario.nombre_completo.like(like),
            Usuario.num_empleado.cast(String).like(like),
            Usuario.code_externo.like(like),
            Usuario.departamento.like(like),
            Usuario.puesto.like(like),
            Usuario.empresa.like(like),
        ]
        stmt = stmt.where(or_(*campos))
    stmt = stmt.order_by(Usuario.nombre_completo).limit(25)
    rows = db.scalars(stmt).all()

    def coincide(valor, needle):
        return bool(needle) and valor is not None and needle.lower() in str(valor).lower()

    resultados = []
    for u in rows:
        campos_coinciden = [
            etiqueta
            for etiqueta, valor in [
                ("nombre", u.nombre_completo),
                ("No. empleado", u.num_empleado),
                ("código", u.code_externo),
                ("puesto", u.puesto),
                ("departamento", u.departamento),
                ("empresa", u.empresa),
            ]
            if coincide(valor, q)
        ]
        resultados.append(
            {
                "id_usuario": u.id_usuario,
                "nombre_completo": u.nombre_completo,
                "num_empleado": u.num_empleado,
                "code_externo": u.code_externo,
                "puesto": u.puesto,
                "departamento": u.departamento,
                "empresa": u.empresa,
                "foto_url": decode_img(u.img_empleado),
                "coincide_en": campos_coinciden,
            }
        )
    return resultados


@app.post("/api/tests", response_model=dict)
def crear_test(payload: TestIn, request: Request, db: Session = Depends(get_db)):
    # Catalogo y validacion de respuestas.
    preguntas_db = db.scalars(select(FatigaPregunta)).all()
    criticas = {p.id_pregunta for p in preguntas_db if p.critica}
    validos = {p.id_pregunta for p in preguntas_db}

    respuestas = {r.id_pregunta: r.valor for r in payload.respuestas}
    faltantes = validos - set(respuestas)
    if faltantes:
        raise HTTPException(status_code=422, detail=f"Faltan respuestas: {sorted(faltantes)}")
    if len(payload.respuestas) != len(validos):
        raise HTTPException(status_code=422, detail="Debe responder las 10 preguntas exactamente una vez.")

    # La identidad debe venir de la lista de empleados (no hay captura manual).
    if payload.id_usuario is None:
        raise HTTPException(
            status_code=422,
            detail="Debe identificar al trabajador seleccionándolo de la lista.",
        )
    usuario = db.get(Usuario, payload.id_usuario)
    if not usuario or usuario.estatus != 1:
        raise HTTPException(status_code=422, detail="Trabajador no válido o inactivo.")

    resultado = scoring.calcular(respuestas, criticas)

    test = FatigaTest(
        id_usuario=usuario.id_usuario,
        num_empleado=usuario.num_empleado,
        nombre_completo=usuario.nombre_completo,
        puesto=usuario.puesto,
        departamento=usuario.departamento,
        empresa=usuario.empresa,
        turno=payload.turno,
        hora_entrada=parse_time(payload.hora_entrada),
        fecha=payload.fecha or date.today(),
        puntaje_total=resultado["puntaje_total"],
        semaforo=resultado["semaforo"],
        critica_con_2pts=1 if resultado["critica_con_2pts"] else 0,
        jornada_extra=resultado["jornada_extra"],
        accion_tomada=payload.accion_tomada,
        observaciones=payload.observaciones,
        firma_trabajador=payload.firma_trabajador,
        validador_nombre=payload.validador_nombre,
        ip_origen=request.client.host if request.client else None,
    )
    db.add(test)
    db.flush()
    for pid, valor in respuestas.items():
        db.add(FatigaRespuesta(id_test=test.id_test, id_pregunta=pid, valor=valor))
    if payload.firma_imagen:
        db.add(FatigaFirma(id_test=test.id_test, firma_imagen=payload.firma_imagen))
    db.commit()
    db.refresh(test)

    return {"ok": True, "id_test": test.id_test, **resultado}


# --------------------------------------------------------------------------
# Endpoints de supervisor (requieren token)
# --------------------------------------------------------------------------
def _to_out(t: FatigaTest) -> TestOut:
    return TestOut(
        id_test=t.id_test, id_usuario=t.id_usuario, num_empleado=t.num_empleado,
        nombre_completo=t.nombre_completo, puesto=t.puesto, departamento=t.departamento,
        empresa=t.empresa, turno=t.turno, hora_entrada=t.hora_entrada, fecha=t.fecha,
        puntaje_total=t.puntaje_total, semaforo=t.semaforo,
        critica_con_2pts=bool(t.critica_con_2pts), jornada_extra=t.jornada_extra,
        accion_tomada=t.accion_tomada, observaciones=t.observaciones,
        firma_trabajador=t.firma_trabajador, validador_nombre=t.validador_nombre,
        creado_en=t.creado_en.isoformat() if t.creado_en else None,
    )


@app.get("/api/tests", dependencies=[Depends(require_reports)])
def listar_tests(
    fecha: Optional[str] = None,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    semaforo: Optional[str] = None,
    departamento: Optional[str] = None,
    turno: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = Query(default=200, le=1000),
    db: Session = Depends(get_db),
):
    stmt = select(FatigaTest)
    if fecha:
        stmt = stmt.where(FatigaTest.fecha == fecha)
    if desde:
        stmt = stmt.where(FatigaTest.fecha >= desde)
    if hasta:
        stmt = stmt.where(FatigaTest.fecha <= hasta)
    if semaforo:
        stmt = stmt.where(FatigaTest.semaforo == semaforo.upper())
    if departamento:
        stmt = stmt.where(FatigaTest.departamento == departamento)
    if turno:
        stmt = stmt.where(FatigaTest.turno == turno)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            (FatigaTest.nombre_completo.like(like))
            | (FatigaTest.num_empleado.cast(String).like(like))
        )
    stmt = stmt.order_by(FatigaTest.creado_en.desc()).limit(limit)
    rows = db.scalars(stmt).all()
    return [_to_out(t).model_dump() for t in rows]


@app.get("/api/tests/{id_test}", dependencies=[Depends(require_reports)])
def detalle_test(id_test: int, db: Session = Depends(get_db)):
    t = db.get(FatigaTest, id_test)
    if not t:
        raise HTTPException(status_code=404, detail="Test no encontrado")
    preguntas_db = db.scalars(select(FatigaPregunta)).all()
    catalog = {p.id_pregunta: p for p in preguntas_db}
    criticas = {p.id_pregunta for p in preguntas_db if p.critica}
    respuestas = db.scalars(
        select(FatigaRespuesta).where(FatigaRespuesta.id_test == id_test)
    ).all()
    resp_map = {r.id_pregunta: r.valor for r in respuestas}
    res = scoring.calcular(resp_map, criticas)
    out = _to_out(t).model_dump()
    out["respuestas"] = [
        {
            "id_pregunta": pid,
            "valor": resp_map[pid],
            "texto": catalog[pid].texto if pid in catalog else "",
            "opcion": (
                [catalog[pid].opcion_0, catalog[pid].opcion_1, catalog[pid].opcion_2][resp_map[pid]]
                if pid in catalog else ""
            ),
            "critica": pid in criticas,
        }
        for pid in sorted(resp_map)
    ]
    out["criticas_con_2pts"] = res["criticas_con_2pts"]
    out["recomendacion"] = res["recomendacion"]
    firma = db.get(FatigaFirma, id_test)
    out["firma_imagen"] = firma.firma_imagen if firma else None
    return out


@app.get("/api/resumen", dependencies=[Depends(require_reports)])
def resumen(
    fecha: Optional[str] = None,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Totales en un rango de fechas (desde–hasta) + patron repetido en el rango."""
    if not desde and not hasta:
        desde = hasta = fecha or date.today().isoformat()
    else:
        desde = desde or hasta
        hasta = hasta or desde
    if desde > hasta:
        desde, hasta = hasta, desde

    rows = db.execute(
        text(
            "SELECT semaforo, COUNT(*), SUM(critica_con_2pts) "
            "FROM fatiga_tests WHERE fecha BETWEEN :d1 AND :d2 GROUP BY semaforo"
        ),
        {"d1": desde, "d2": hasta},
    ).all()
    conteo = {"VERDE": 0, "AMARILLO": 0, "ROJO": 0}
    criticas = 0
    for sem, n, cr in rows:
        conteo[sem] = int(n)
        criticas += int(cr or 0)

    # Patron repetido: empleados con 2+ dias en amarillo/rojo dentro del rango.
    patron = db.execute(
        text(
            "SELECT COALESCE(id_usuario, -1) uid, COALESCE(num_empleado, -1) ne, "
            "       MAX(nombre_completo) nombre, COUNT(DISTINCT fecha) dias "
            "FROM fatiga_tests "
            "WHERE fecha BETWEEN :d1 AND :d2 AND semaforo IN ('AMARILLO','ROJO') "
            "GROUP BY COALESCE(id_usuario, -1), COALESCE(num_empleado, -1) "
            "HAVING dias >= 2 ORDER BY dias DESC LIMIT 50"
        ),
        {"d1": desde, "d2": hasta},
    ).all()

    return {
        "desde": desde,
        "hasta": hasta,
        "fecha": hasta,
        "total": sum(conteo.values()),
        "verde": conteo["VERDE"],
        "amarillo": conteo["AMARILLO"],
        "rojo": conteo["ROJO"],
        "criticas_2pts": criticas,
        "patron_repetido": [
            {"id_usuario": r[0], "num_empleado": r[1], "nombre": r[2], "dias": int(r[3])}
            for r in patron
        ],
    }


@app.get("/api/empleados/{id_usuario}/historial", dependencies=[Depends(require_reports)])
def historial(id_usuario: int, limite: int = 30, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(FatigaTest)
        .where(FatigaTest.id_usuario == id_usuario)
        .order_by(FatigaTest.fecha.desc(), FatigaTest.id_test.desc())
        .limit(limite)
    ).all()
    return [_to_out(t).model_dump() for t in rows]


# --------------------------------------------------------------------------
# Frontend estatico
# --------------------------------------------------------------------------
@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


app.mount("/", StaticFiles(directory=str(FRONTEND), html=True), name="frontend")
