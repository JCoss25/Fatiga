"""API del modulo CAR · Tarjeta de control y administración de riesgos.

Flujo:
- El formulario público emite la tarjeta (partes 1 a 4 + firma del emisor).
- El panel administrativo consulta por folio y completa la parte 5
  (responsable, firma y cierre del hallazgo). Solo el rol admin puede cerrar.
"""
import os
import uuid
from datetime import date
from pathlib import Path
from typing import List, Optional

from fastapi import (
    APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile,
)
from fastapi.responses import FileResponse
from sqlalchemy import String, delete, func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..auth import require_admin, require_reports, role_for
from ..db import get_db as main_get_db
from ..models import Usuario
from ..tz import ahora, hoy
from .db import ROOT, get_db, init_local_schema
from .models import (
    CarArea, CarEvidencia, CarTarjeta, CarUbicacion, CarZona, CarZonaArea,
)
from .schemas import (
    CarAreaIn, CarAreaOut, CarCatalogosOut, CarCierreIn, CarDetalleOut,
    CarEmpleadoOut, CarEvidenciaOut, CarListaOut, CarTarjetaIn,
    CarZonaIn, CarZonaOut, CarZonaUpdate,
)

router = APIRouter(prefix="/api/car", tags=["CAR · Tarjeta de riesgos"])

# Crea las tablas locales (solo SQLite). En MySQL se usa db/migrate_car.py.
init_local_schema()

EVIDENCIAS_DIR = ROOT / "data" / "car_evidencias"
EVIDENCIAS_DIR.mkdir(parents=True, exist_ok=True)

MAX_FOTO_MB = int(os.getenv("CAR_MAX_FOTO_MB", "12"))
MAX_VIDEO_MB = int(os.getenv("CAR_MAX_VIDEO_MB", "80"))
CLOUDFRONT_BASE = "https://dvctlemkfvc4i.cloudfront.net/"

def _decode_img(raw) -> Optional[str]:
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


def _buscar_en_fatiga(q: str, db: Session) -> List[dict]:
    stmt = select(Usuario).where(Usuario.estatus == 1)
    q = (q or "").strip()
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(
            Usuario.nombre_completo.like(like),
            Usuario.num_empleado.cast(String).like(like),
            Usuario.code_externo.like(like),
            Usuario.departamento.like(like),
            Usuario.puesto.like(like),
            Usuario.empresa.like(like),
        ))
    rows = db.scalars(stmt.order_by(Usuario.nombre_completo).limit(25)).all()
    return [
        {
            "id_usuario": u.id_usuario,
            "nombre_completo": u.nombre_completo,
            "num_empleado": u.num_empleado,
            "departamento": u.departamento,
            "puesto": u.puesto,
            "empresa": u.empresa,
            "foto_url": _decode_img(u.img_empleado),
            "fuente": "fatiga",
        }
        for u in rows
    ]


def _empleado_para_tarjeta(id_usuario: int, db: Session) -> Optional[dict]:
    try:
        u = db.get(Usuario, id_usuario)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail="No se pudo consultar la base de empleados. Revisa la conexión a RDS.",
        ) from exc
    if not u or u.estatus != 1:
        return None
    return {
        "id_usuario": u.id_usuario,
        "nombre_completo": u.nombre_completo,
        "num_empleado": u.num_empleado,
        "departamento": u.departamento,
        "puesto": u.puesto,
        "empresa": u.empresa,
        "foto_url": _decode_img(u.img_empleado),
        "fuente": "fatiga",
    }


def _ev_out(e: CarEvidencia) -> CarEvidenciaOut:
    return CarEvidenciaOut(
        id_evidencia=e.id_evidencia,
        tipo=e.tipo,
        nombre=e.nombre,
        mime=e.mime,
        tamano=e.tamano,
        url=f"api/car/evidencias/archivo/{e.archivo}",
    )


def _lista_out(t: CarTarjeta, ub: Optional[CarUbicacion] = None) -> CarListaOut:
    return CarListaOut(
        id_tarjeta=t.id_tarjeta,
        folio=t.folio,
        fecha=t.fecha,
        observador=t.observador,
        num_empleado=t.num_empleado,
        area=t.area,
        zona=ub.zona_nombre if ub else None,
        tipo=t.tipo,
        clasificacion=t.clasificacion,
        controlado=t.controlado,
        estado=t.estado,
        evidencias=len(t.evidencias or []),
        fecha_cierre=t.fecha_cierre,
        responsable=t.responsable,
        creado_en=t.creado_en.isoformat() if t.creado_en else None,
    )


def _detalle_out(t: CarTarjeta, ub: Optional[CarUbicacion] = None) -> CarDetalleOut:
    base = _lista_out(t, ub)
    return CarDetalleOut(
        **base.model_dump(),
        descripcion=t.descripcion,
        lat=ub.lat if ub else None,
        lng=ub.lng if ub else None,
        origen_geo=ub.origen if ub else None,
        acciones_inmediatas=t.acciones_inmediatas,
        acciones_definitivas=t.acciones_definitivas,
        fecha_compromiso=t.fecha_compromiso,
        firma_emisor=t.firma_emisor,
        firma_responsable=t.firma_responsable,
        area_responsable=t.area_responsable,
        comentario_cierre=t.comentario_cierre,
        revision=bool(t.revision),
        cerrado_en=t.cerrado_en.isoformat() if t.cerrado_en else None,
        lista_evidencias=[_ev_out(e) for e in t.evidencias],
    )


def _nuevo_folio(db: Session, year: int) -> str:
    prefix = f"CAR-{year}-"
    last = db.scalar(
        select(func.max(CarTarjeta.folio)).where(CarTarjeta.folio.like(prefix + "%"))
    )
    n = 1
    if last:
        try:
            n = int(str(last).rsplit("-", 1)[1]) + 1
        except (ValueError, IndexError):
            n = 1
    while True:
        folio = f"{prefix}{n:03d}"
        exists = db.scalar(select(CarTarjeta.id_tarjeta).where(CarTarjeta.folio == folio))
        if not exists:
            return folio
        n += 1


# --------------------------------------------------------------------------
# Catálogos y empleados
# --------------------------------------------------------------------------
@router.get("/empleados", response_model=List[CarEmpleadoOut])
def empleados(q: str = Query(default="", max_length=80), db: Session = Depends(main_get_db)):
    """Busca al observador en la misma tabla `usuarios` que alimenta Fatiga.

    Si RDS no está disponible en el equipo local, responde con un directorio
    de ejemplo y lo marca con fuente="local".
    """
    try:
        return _buscar_en_fatiga(q, db)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail="No se pudo consultar la base de empleados. Revisa la conexión a RDS.",
        ) from exc


def _zonas_out(db: Session) -> List[CarZonaOut]:
    zonas = db.scalars(
        select(CarZona).where(CarZona.activo == 1).order_by(CarZona.nombre)
    ).all()
    areas = db.scalars(select(CarArea).where(CarArea.activo == 1).order_by(CarArea.nombre)).all()
    area_map = {a.id_area: a for a in areas}
    mapping = db.scalars(select(CarZonaArea)).all()
    out = []
    for z in zonas:
        ids = [m.id_area for m in mapping if m.id_zona == z.id_zona]
        out.append(CarZonaOut(
            id_zona=z.id_zona,
            nombre=z.nombre,
            lat=z.lat,
            lng=z.lng,
            radio_m=z.radio_m,
            areas=[
                CarAreaOut(id=area_map[i].id_area, nombre=area_map[i].nombre)
                for i in ids if i in area_map
            ],
        ))
    return out


@router.get("/catalogos", response_model=CarCatalogosOut)
def catalogos(db: Session = Depends(get_db)):
    areas = db.scalars(
        select(CarArea).where(CarArea.activo == 1).order_by(CarArea.nombre)
    ).all()
    return CarCatalogosOut(
        areas=[CarAreaOut(id=a.id_area, nombre=a.nombre) for a in areas],
        zonas=_zonas_out(db),
    )


# --------------------------------------------------------------------------
# Zonas y geocercas (administradas desde el panel)
# --------------------------------------------------------------------------
@router.post("/zonas", response_model=CarZonaOut, dependencies=[Depends(require_admin)])
def agregar_zona(payload: CarZonaIn, db: Session = Depends(get_db)):
    nombre = payload.nombre.strip().upper()
    if len(nombre) < 2:
        raise HTTPException(status_code=422, detail="Escribe una zona válida.")
    existing = db.scalar(select(CarZona).where(func.lower(CarZona.nombre) == func.lower(nombre)))
    if existing:
        existing.activo = 1
        existing.nombre = nombre
        if payload.lat is not None: existing.lat = payload.lat
        if payload.lng is not None: existing.lng = payload.lng
        existing.radio_m = payload.radio_m
        db.commit()
        db.refresh(existing)
        return CarZonaOut(id_zona=existing.id_zona, nombre=existing.nombre,
                          lat=existing.lat, lng=existing.lng, radio_m=existing.radio_m)
    item = CarZona(nombre=nombre, lat=payload.lat, lng=payload.lng,
                   radio_m=payload.radio_m, activo=1)
    db.add(item)
    db.commit()
    db.refresh(item)
    return CarZonaOut(id_zona=item.id_zona, nombre=item.nombre,
                      lat=item.lat, lng=item.lng, radio_m=item.radio_m)


@router.put("/zonas/{id_zona}", response_model=CarZonaOut, dependencies=[Depends(require_admin)])
def actualizar_zona(id_zona: int, payload: CarZonaUpdate, db: Session = Depends(get_db)):
    z = db.get(CarZona, id_zona)
    if not z:
        raise HTTPException(status_code=404, detail="Zona no encontrada")
    if payload.lat is not None:
        z.lat = payload.lat
    if payload.lng is not None:
        z.lng = payload.lng
    if payload.radio_m is not None:
        z.radio_m = payload.radio_m
    db.commit()
    db.refresh(z)
    return CarZonaOut(id_zona=z.id_zona, nombre=z.nombre, lat=z.lat, lng=z.lng, radio_m=z.radio_m)


@router.post("/zonas/{id_zona}/areas/{id_area}", dependencies=[Depends(require_admin)])
def asignar_area_zona(id_zona: int, id_area: int, db: Session = Depends(get_db)):
    if not db.get(CarZona, id_zona):
        raise HTTPException(status_code=404, detail="Zona no encontrada")
    if not db.get(CarArea, id_area):
        raise HTTPException(status_code=404, detail="Área no encontrada")
    if not db.get(CarZonaArea, (id_zona, id_area)):
        db.add(CarZonaArea(id_zona=id_zona, id_area=id_area))
        db.commit()
    return {"ok": True}


@router.delete("/zonas/{id_zona}/areas/{id_area}", dependencies=[Depends(require_admin)])
def quitar_area_zona(id_zona: int, id_area: int, db: Session = Depends(get_db)):
    db.execute(delete(CarZonaArea).where(
        CarZonaArea.id_zona == id_zona, CarZonaArea.id_area == id_area))
    db.commit()
    return {"ok": True}


@router.post("/areas", response_model=CarAreaOut, dependencies=[Depends(require_admin)])
def agregar_area(payload: CarAreaIn, db: Session = Depends(get_db)):
    nombre = payload.nombre.strip()
    if len(nombre) < 2:
        raise HTTPException(status_code=422, detail="Escribe un área válida.")
    if payload.id_zona and not db.get(CarZona, payload.id_zona):
        raise HTTPException(status_code=422, detail="La zona no existe.")
    existing = db.scalar(select(CarArea).where(func.lower(CarArea.nombre) == func.lower(nombre)))
    if existing:
        existing.activo = 1
        existing.nombre = nombre
        item = existing
    else:
        item = CarArea(nombre=nombre, activo=1)
        db.add(item)
    db.commit()
    db.refresh(item)
    if payload.id_zona and not db.get(CarZonaArea, (payload.id_zona, item.id_area)):
        db.add(CarZonaArea(id_zona=payload.id_zona, id_area=item.id_area))
        db.commit()
    return CarAreaOut(id=item.id_area, nombre=item.nombre)


@router.delete("/areas/{id_area}", dependencies=[Depends(require_admin)])
def borrar_area(id_area: int, db: Session = Depends(get_db)):
    item = db.get(CarArea, id_area)
    if not item:
        raise HTTPException(status_code=404, detail="Área no encontrada")
    item.activo = 0
    db.execute(delete(CarZonaArea).where(CarZonaArea.id_area == id_area))
    db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------
# Evidencias
# --------------------------------------------------------------------------
@router.post("/evidencias", response_model=CarEvidenciaOut)
async def subir_evidencia(
    tipo: str = Form(...),
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    tipo = (tipo or "").strip().upper()
    if tipo not in ("FOTO", "VIDEO"):
        raise HTTPException(status_code=422, detail="El tipo debe ser FOTO o VIDEO.")
    mime = (archivo.content_type or "").lower()
    if tipo == "FOTO" and not mime.startswith("image/"):
        raise HTTPException(status_code=422, detail="El archivo no es una imagen válida.")
    if tipo == "VIDEO" and not mime.startswith("video/"):
        raise HTTPException(status_code=422, detail="El archivo no es un video válido.")

    ext = Path(archivo.filename or "").suffix.lower()
    if not ext or len(ext) > 10:
        ext = ".jpg" if tipo == "FOTO" else ".mp4"
    nombre = Path(archivo.filename or f"evidencia{ext}").name[:255]
    archivo_id = uuid.uuid4().hex + ext
    destino = EVIDENCIAS_DIR / archivo_id
    limite = (MAX_FOTO_MB if tipo == "FOTO" else MAX_VIDEO_MB) * 1024 * 1024

    tamano = 0
    try:
        with destino.open("wb") as out:
            while True:
                chunk = await archivo.read(1024 * 1024)
                if not chunk:
                    break
                tamano += len(chunk)
                if tamano > limite:
                    raise HTTPException(
                        status_code=413,
                        detail=f"El archivo supera el límite de {limite // (1024 * 1024)} MB.",
                    )
                out.write(chunk)
    except HTTPException:
        destino.unlink(missing_ok=True)
        raise
    except Exception as exc:  # noqa: BLE001
        destino.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"No se pudo guardar la evidencia: {exc}") from exc

    if tamano == 0:
        destino.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="El archivo está vacío.")

    ev = CarEvidencia(
        tipo=tipo, nombre=nombre, mime=mime or "application/octet-stream",
        tamano=tamano, archivo=archivo_id,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return _ev_out(ev)


@router.get("/evidencias/archivo/{archivo}")
def ver_archivo(
    archivo: str,
    token: Optional[str] = Query(default=None),
    x_admin_token: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    if not role_for(token or x_admin_token):
        raise HTTPException(status_code=401, detail="Se requiere clave de reportes")
    if Path(archivo).name != archivo:
        raise HTTPException(status_code=404, detail="Evidencia no encontrada")
    ev = db.scalar(select(CarEvidencia).where(CarEvidencia.archivo == archivo))
    path = EVIDENCIAS_DIR / archivo
    if not ev or not path.is_file():
        raise HTTPException(status_code=404, detail="Evidencia no encontrada")
    return FileResponse(
        path, media_type=ev.mime, filename=ev.nombre,
        content_disposition_type="inline",
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.delete("/evidencias/{id_evidencia}")
def borrar_evidencia(id_evidencia: int, db: Session = Depends(get_db)):
    ev = db.get(CarEvidencia, id_evidencia)
    if not ev:
        raise HTTPException(status_code=404, detail="Evidencia no encontrada")
    if ev.id_tarjeta:
        raise HTTPException(status_code=409, detail="La evidencia ya está ligada a una tarjeta.")
    (EVIDENCIAS_DIR / ev.archivo).unlink(missing_ok=True)
    db.delete(ev)
    db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------
# Tarjetas
# --------------------------------------------------------------------------
@router.post("", response_model=dict)
def crear_tarjeta(
    payload: CarTarjetaIn,
    request: Request,
    db: Session = Depends(get_db),
    main_db: Session = Depends(main_get_db),
):
    empleado = _empleado_para_tarjeta(payload.id_usuario, main_db)
    if not empleado:
        raise HTTPException(status_code=422, detail="El observador no existe o está inactivo.")

    area = db.scalar(
        select(CarArea).where(CarArea.nombre == payload.area.strip(), CarArea.activo == 1)
    )
    if not area:
        raise HTTPException(status_code=422, detail="Selecciona un área registrada en el catálogo CAR.")

    zona = None
    if payload.id_zona:
        zona = db.get(CarZona, payload.id_zona)
        if not zona or zona.activo != 1:
            raise HTTPException(status_code=422, detail="Selecciona una zona válida.")
        # Si la zona ya tiene áreas configuradas, el área debe pertenecer a ella.
        configuradas = db.scalar(
            select(func.count()).select_from(CarZonaArea).where(CarZonaArea.id_zona == zona.id_zona)
        ) or 0
        if configuradas and not db.get(CarZonaArea, (zona.id_zona, area.id_area)):
            raise HTTPException(
                status_code=422,
                detail="El área no pertenece a la zona seleccionada.",
            )

    if not payload.firma_emisor.startswith("data:image/png;base64,"):
        raise HTTPException(status_code=422, detail="Falta la firma del emisor.")

    evidencias: List[CarEvidencia] = []
    if payload.evidencias:
        ids = list(dict.fromkeys(payload.evidencias))
        evidencias = db.scalars(
            select(CarEvidencia).where(
                CarEvidencia.id_evidencia.in_(ids),
                CarEvidencia.id_tarjeta.is_(None),
            )
        ).all()
        if len(evidencias) != len(ids):
            raise HTTPException(status_code=422, detail="Una evidencia no existe o ya fue utilizada.")

    folio = _nuevo_folio(db, payload.fecha.year)
    tarjeta = CarTarjeta(
        folio=folio,
        fecha=payload.fecha,
        id_usuario=empleado["id_usuario"],
        observador=empleado["nombre_completo"],
        num_empleado=empleado.get("num_empleado"),
        area=area.nombre,
        tipo=payload.tipo,
        descripcion=payload.descripcion.strip(),
        controlado=payload.controlado,
        clasificacion=payload.clasificacion,
        acciones_inmediatas=(payload.acciones_inmediatas or "").strip() or None,
        acciones_definitivas=(payload.acciones_definitivas or "").strip() or None,
        fecha_compromiso=payload.fecha_compromiso,
        firma_emisor=payload.firma_emisor,
        estado="PENDIENTE",
        revision=0,
        ip_origen=request.client.host if request.client else None,
    )
    db.add(tarjeta)
    db.flush()
    db.add(CarUbicacion(
        id_tarjeta=tarjeta.id_tarjeta,
        id_zona=zona.id_zona if zona else None,
        zona_nombre=zona.nombre if zona else None,
        lat=payload.lat,
        lng=payload.lng,
        origen=(payload.origen_geo or "MANUAL")[:10],
    ))
    for ev in evidencias:
        ev.id_tarjeta = tarjeta.id_tarjeta
    db.commit()
    db.refresh(tarjeta)
    return {
        "ok": True,
        "id_tarjeta": tarjeta.id_tarjeta,
        "folio": tarjeta.folio,
        "estado": tarjeta.estado,
        "evidencias": len(evidencias),
    }


@router.get("/resumen", dependencies=[Depends(require_reports)])
def resumen(
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    estado: Optional[str] = None,
    clasificacion: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
):
    stmt = select(CarTarjeta).options(selectinload(CarTarjeta.evidencias))
    if desde:
        stmt = stmt.where(CarTarjeta.fecha >= desde)
    if hasta:
        stmt = stmt.where(CarTarjeta.fecha <= hasta)
    if estado:
        stmt = stmt.where(CarTarjeta.estado == estado)
    if clasificacion:
        stmt = stmt.where(CarTarjeta.clasificacion == clasificacion)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(
            CarTarjeta.folio.like(like),
            CarTarjeta.observador.like(like),
            CarTarjeta.area.like(like),
            CarTarjeta.descripcion.like(like),
            CarTarjeta.responsable.like(like),
        ))
    rows = db.scalars(stmt).all()
    return {
        "total": len(rows),
        "pendientes": sum(1 for t in rows if t.estado == "PENDIENTE"),
        "cerrados": sum(1 for t in rows if t.estado == "CERRADO"),
        "rojos": sum(1 for t in rows if t.clasificacion == "ROJO"),
        "amarillos": sum(1 for t in rows if t.clasificacion == "AMARILLO"),
        "con_evidencia": sum(1 for t in rows if t.evidencias),
        "areas": len({t.area for t in rows}),
    }


@router.get("", response_model=List[CarListaOut], dependencies=[Depends(require_reports)])
def listar(
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    estado: Optional[str] = None,
    clasificacion: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = Query(default=300, le=1000),
    db: Session = Depends(get_db),
):
    stmt = select(CarTarjeta).options(selectinload(CarTarjeta.evidencias))
    if desde:
        stmt = stmt.where(CarTarjeta.fecha >= desde)
    if hasta:
        stmt = stmt.where(CarTarjeta.fecha <= hasta)
    if estado:
        stmt = stmt.where(CarTarjeta.estado == estado)
    if clasificacion:
        stmt = stmt.where(CarTarjeta.clasificacion == clasificacion)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(
            CarTarjeta.folio.like(like),
            CarTarjeta.observador.like(like),
            CarTarjeta.area.like(like),
            CarTarjeta.descripcion.like(like),
            CarTarjeta.responsable.like(like),
        ))
    stmt = stmt.order_by(CarTarjeta.fecha.desc(), CarTarjeta.id_tarjeta.desc()).limit(limit)
    rows = db.scalars(stmt).all()
    ids = [t.id_tarjeta for t in rows]
    ubs = {}
    if ids:
        for u in db.scalars(select(CarUbicacion).where(CarUbicacion.id_tarjeta.in_(ids))).all():
            ubs[u.id_tarjeta] = u
    return [_lista_out(t, ubs.get(t.id_tarjeta)) for t in rows]


@router.get("/{id_tarjeta}", response_model=CarDetalleOut, dependencies=[Depends(require_reports)])
def detalle(id_tarjeta: int, db: Session = Depends(get_db)):
    t = db.scalar(
        select(CarTarjeta)
        .options(selectinload(CarTarjeta.evidencias))
        .where(CarTarjeta.id_tarjeta == id_tarjeta)
    )
    if not t:
        raise HTTPException(status_code=404, detail="Tarjeta CAR no encontrada")
    return _detalle_out(t, db.get(CarUbicacion, id_tarjeta))


@router.post("/{id_tarjeta}/cierre", dependencies=[Depends(require_admin)])
def cerrar(id_tarjeta: int, payload: CarCierreIn, db: Session = Depends(get_db)):
    t = db.get(CarTarjeta, id_tarjeta)
    if not t:
        raise HTTPException(status_code=404, detail="Tarjeta CAR no encontrada")
    if t.estado == "CERRADO":
        raise HTTPException(status_code=409, detail="La tarjeta ya está cerrada.")
    if not payload.firma_responsable.startswith("data:image/png;base64,"):
        raise HTTPException(status_code=422, detail="Falta la firma del responsable.")
    if payload.fecha_cierre and payload.fecha_cierre < t.fecha:
        raise HTTPException(status_code=422, detail="La fecha de cierre no puede ser anterior a la emisión.")

    area = db.scalar(
        select(CarArea).where(
            CarArea.nombre == payload.area_responsable.strip(),
            CarArea.activo == 1,
        )
    )
    if not area:
        raise HTTPException(status_code=422, detail="Selecciona un área del catálogo CAR.")

    # Evidencia opcional del cierre
    if payload.evidencias:
        ids = list(dict.fromkeys(payload.evidencias))
        evs = db.scalars(
            select(CarEvidencia).where(
                CarEvidencia.id_evidencia.in_(ids),
                CarEvidencia.id_tarjeta.is_(None),
            )
        ).all()
        if len(evs) != len(ids):
            raise HTTPException(status_code=422, detail="Una evidencia no existe o ya fue utilizada.")
        for ev in evs:
            ev.id_tarjeta = t.id_tarjeta

    t.responsable = payload.responsable.strip()
    t.area_responsable = area.nombre
    t.firma_responsable = payload.firma_responsable
    t.comentario_cierre = payload.comentario_cierre.strip()
    t.revision = 1 if payload.revision else 0
    t.fecha_cierre = payload.fecha_cierre or hoy()
    t.estado = "CERRADO"
    t.cerrado_en = ahora()
    t.cerrado_por = "admin"
    db.commit()
    db.refresh(t)
    return {"ok": True, "folio": t.folio, "estado": t.estado}
