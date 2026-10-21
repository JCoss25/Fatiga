"""Check list de seguridad basada en comportamiento (REG-SST-25).

Modulo aditivo: el test de fatiga y sus tablas no se tocan.
El formulario es publico (sin contrasena); los reportes requieren admin o revisor.
"""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .auth import require_reports
from .db import get_db
from .models import SstAuditoria, SstPregunta, SstRespuesta, Usuario
from .schemas import (
    SstAuditoriaDetalleOut,
    SstAuditoriaIn,
    SstAuditoriaOut,
    SstPreguntaOut,
    SstRespuestaOut,
)

router = APIRouter(prefix="/api/sst", tags=["Seguridad REG-SST-25"])


def _base_query(
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    area: Optional[str] = None,
    auditor: Optional[str] = None,
    q: Optional[str] = None,
    con_hallazgos: Optional[bool] = None,
):
    stmt = select(SstAuditoria)
    if desde:
        stmt = stmt.where(SstAuditoria.fecha >= desde)
    if hasta:
        stmt = stmt.where(SstAuditoria.fecha <= hasta)
    if area:
        stmt = stmt.where(SstAuditoria.area == area)
    if auditor:
        stmt = stmt.where(SstAuditoria.auditor == auditor)
    if con_hallazgos is True:
        stmt = stmt.where(SstAuditoria.inseguras > 0)
    if con_hallazgos is False:
        stmt = stmt.where(SstAuditoria.inseguras == 0)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                SstAuditoria.area.like(like),
                SstAuditoria.departamento.like(like),
                SstAuditoria.auditado.like(like),
                SstAuditoria.auditor.like(like),
            )
        )
    return stmt


def _out(a: SstAuditoria) -> SstAuditoriaOut:
    return SstAuditoriaOut(
        id_auditoria=a.id_auditoria,
        fecha=a.fecha,
        area=a.area,
        departamento=a.departamento,
        auditado=a.auditado,
        auditor=a.auditor,
        seguras=a.seguras,
        inseguras=a.inseguras,
        porcentaje=a.porcentaje,
        creado_en=a.creado_en.isoformat() if a.creado_en else None,
    )


@router.get("/preguntas", response_model=List[SstPreguntaOut])
def preguntas(db: Session = Depends(get_db)):
    """Catalogo publico de las 18 conductas (lo usa el formulario)."""
    rows = db.scalars(select(SstPregunta).order_by(SstPregunta.orden)).all()
    return [SstPreguntaOut(id_pregunta=p.id_pregunta, orden=p.orden, texto=p.texto) for p in rows]


@router.post("", response_model=dict)
def crear_auditoria(payload: SstAuditoriaIn, request: Request, db: Session = Depends(get_db)):
    """Alta publica de una auditoria. No requiere contrasena."""
    preguntas_db = db.scalars(select(SstPregunta)).all()
    validos = {p.id_pregunta for p in preguntas_db}
    if len(validos) != 18:
        raise HTTPException(status_code=503, detail="El catálogo de las 18 conductas no está disponible.")

    nums = [r.n for r in payload.respuestas]
    if len(nums) != 18 or set(nums) != validos:
        raise HTTPException(status_code=422, detail="Debe responder las 18 conductas exactamente una vez.")

    for r in payload.respuestas:
        if r.estado == "INSEGURO" and not (r.observacion or "").strip():
            raise HTTPException(
                status_code=422,
                detail=f"La conducta {r.n} está marcada como insegura y necesita una observación.",
            )

    for nombre, firma in (("trabajador", payload.firma_trabajador), ("auditor", payload.firma_auditor)):
        if not firma.startswith("data:image/png;base64,"):
            raise HTTPException(status_code=422, detail=f"Falta la firma del {nombre}.")

    # La identidad viene de la tabla usuarios (la misma que usa Fatiga).
    usuario = db.get(Usuario, payload.id_usuario)
    if not usuario or usuario.estatus != 1:
        raise HTTPException(status_code=422, detail="Trabajador no válido o inactivo.")

    seguras = sum(1 for r in payload.respuestas if r.estado == "SEGURO")
    inseguras = 18 - seguras
    porcentaje = round((seguras / 18) * 100)

    auditoria = SstAuditoria(
        fecha=payload.fecha,
        area=payload.area.strip(),
        departamento=(usuario.departamento or "").strip() or "Sin departamento",
        auditado=usuario.nombre_completo,
        auditor=payload.auditor.strip(),
        comentarios=(payload.comentarios or "").strip() or None,
        seguras=seguras,
        inseguras=inseguras,
        porcentaje=porcentaje,
        firma_trabajador=payload.firma_trabajador,
        firma_auditor=payload.firma_auditor,
        ip_origen=request.client.host if request.client else None,
    )
    db.add(auditoria)
    db.flush()
    for r in sorted(payload.respuestas, key=lambda x: x.n):
        db.add(
            SstRespuesta(
                id_auditoria=auditoria.id_auditoria,
                n=r.n,
                estado=r.estado,
                observacion=(r.observacion or "").strip() or None,
            )
        )
    db.commit()
    db.refresh(auditoria)
    return {
        "ok": True,
        "id_auditoria": auditoria.id_auditoria,
        "seguras": seguras,
        "inseguras": inseguras,
        "porcentaje": porcentaje,
    }


@router.get("/resumen", dependencies=[Depends(require_reports)])
def resumen(
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    area: Optional[str] = None,
    auditor: Optional[str] = None,
    q: Optional[str] = None,
    con_hallazgos: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    rows = db.scalars(_base_query(desde, hasta, area, auditor, q, con_hallazgos)).all()
    total = len(rows)
    seguras = sum(a.seguras for a in rows)
    inseguras = sum(a.inseguras for a in rows)
    con_hallazgos_total = sum(1 for a in rows if a.inseguras > 0)
    return {
        "total": total,
        "seguras": seguras,
        "inseguras": inseguras,
        "porcentaje": round((seguras / (total * 18)) * 100) if total else 0,
        "con_hallazgos": con_hallazgos_total,
        "areas": len({a.area for a in rows}),
    }


@router.get("", dependencies=[Depends(require_reports)])
def listar(
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    area: Optional[str] = None,
    auditor: Optional[str] = None,
    q: Optional[str] = None,
    con_hallazgos: Optional[bool] = None,
    limit: int = Query(default=200, le=1000),
    db: Session = Depends(get_db),
):
    stmt = _base_query(desde, hasta, area, auditor, q, con_hallazgos)
    stmt = stmt.order_by(SstAuditoria.fecha.desc(), SstAuditoria.id_auditoria.desc()).limit(limit)
    return [_out(a).model_dump() for a in db.scalars(stmt).all()]


@router.get("/{id_auditoria}", response_model=SstAuditoriaDetalleOut, dependencies=[Depends(require_reports)])
def detalle(id_auditoria: int, db: Session = Depends(get_db)):
    a = db.get(SstAuditoria, id_auditoria)
    if not a:
        raise HTTPException(status_code=404, detail="Auditoría no encontrada")

    preguntas = {p.id_pregunta: p.texto for p in db.scalars(select(SstPregunta)).all()}
    respuestas = db.scalars(
        select(SstRespuesta).where(SstRespuesta.id_auditoria == id_auditoria).order_by(SstRespuesta.n)
    ).all()

    out = _out(a)
    return SstAuditoriaDetalleOut(
        **out.model_dump(),
        comentarios=a.comentarios,
        firma_trabajador=a.firma_trabajador,
        firma_auditor=a.firma_auditor,
        respuestas=[
            SstRespuestaOut(
                n=r.n,
                estado=r.estado,
                observacion=r.observacion,
                texto=preguntas.get(r.n, ""),
            )
            for r in respuestas
        ],
    )
