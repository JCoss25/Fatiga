"""API del modulo de Cotizacion de danos (Orden de Reparacion TOT).

Flujo:
  solicitante crea/edita -> envia -> aprobador revisa, comenta, aprueba o rechaza.
  Si sigue pendiente despues de DIAS_RECORDATORIO, se manda recordatorio por correo.
"""
import base64
import binascii
import os
import uuid
from datetime import date, datetime, timedelta
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .auth import identidad, require_any, require_aprobador, require_solicitante, role_for
from .correo import (
    correo_decision,
    correo_recordatorio,
    correo_solicitud,
    enviar,
)
from .db import get_db
from .models import CotAdjunto, CotCatalogo, CotComentario, CotCorreo, CotSolicitud
from .schemas import AdjuntoIn, CambioEstatusIn, CatalogoIn, ComentarioIn, DecisionIn, SolicitudIn

router = APIRouter(prefix="/api/comercial", tags=["Comercial · Cotización de daños"])

DIAS_RECORDATORIO = int(os.getenv("DIAS_RECORDATORIO", "2"))
HORAS_ENTRE_RECORDATORIOS = int(os.getenv("HORAS_ENTRE_RECORDATORIOS", "48"))
MAX_ADJUNTO_BYTES = int(os.getenv("MAX_ADJUNTO_MB", "6")) * 1024 * 1024


@router.get("/ping")
def ping():
    return {"ok": True, "app": "comercial"}


@router.post("/login")
def login(x_cot_token: Optional[str] = Header(default=None)):
    role = role_for(x_cot_token)
    if not role:
        raise HTTPException(status_code=401, detail="Clave incorrecta")
    ident = identidad(role)
    return {"ok": True, "role": role, "nombre": ident["nombre"], "email": ident["email"]}


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------
def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat(timespec="seconds") if dt else None


def _num(valor, default=0.0) -> float:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return default


def _total(cantidad, precio) -> float:
    return round(_num(cantidad, 1) * _num(precio, 0), 2)


def _aplicar(sol: CotSolicitud, payload: SolicitudIn) -> None:
    sol.serie = payload.serie or "LC"
    sol.fecha_solicitud = payload.fecha_solicitud or sol.fecha_solicitud or date.today()
    sol.solicitante_cliente = (payload.solicitante_cliente or "").strip()
    sol.vin = (payload.vin or "").strip().upper()
    sol.ubicacion = (payload.ubicacion or "").strip()
    sol.tipo_servicio = (payload.tipo_servicio or "").strip()
    sol.no_parte = (payload.no_parte or "").strip()
    sol.descripcion = (payload.descripcion or "").strip()
    sol.cantidad = _num(payload.cantidad, 1)
    sol.alcance_servicio = (payload.alcance_servicio or "").strip()
    sol.proveedor_sugerido = (payload.proveedor_sugerido or "").strip()
    sol.precio = _num(payload.precio, 0)
    sol.moneda = (payload.moneda or "MXN").upper()
    sol.fecha_requerida = payload.fecha_requerida
    sol.observaciones = (payload.observaciones or "").strip() or None
    sol.datos = payload.datos or {}
    sol.total = _total(sol.cantidad, sol.precio)


def _folio(serie: str, numero: int) -> str:
    """Folio con un solo consecutivo global (no se reinicia por serie).

    El numero es el id autoincrementable de la solicitud, por lo que la
    secuencia es unica para LC y NDVC: TOT-LC-0001, TOT-NDVC-0002, ...
    """
    return f"TOT-{serie or 'LC'}-{numero:04d}"


def _get_sol(db: Session, id_solicitud: int, role: str) -> CotSolicitud:
    sol = db.get(CotSolicitud, id_solicitud)
    if not sol:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    if role == "solicitante" and sol.creado_por_rol != "solicitante":
        raise HTTPException(status_code=403, detail="No tienes acceso a esta solicitud")
    if role == "aprobador" and sol.estatus == "BORRADOR":
        raise HTTPException(status_code=403, detail="La solicitud todavía es un borrador")
    return sol


def _dias(sol: CotSolicitud) -> int:
    base = sol.enviada_en
    fin = sol.aprobada_en or sol.rechazada_en or datetime.now()
    if not base:
        return 0
    return max(0, int((fin - base).total_seconds() // 86400))


def _out(sol: CotSolicitud) -> dict:
    pendiente = sol.estatus == "PENDIENTE"
    return {
        "id_solicitud": sol.id_solicitud,
        "folio": sol.folio,
        "serie": sol.serie,
        "estatus": sol.estatus,
        "fecha_solicitud": sol.fecha_solicitud.isoformat() if sol.fecha_solicitud else None,
        "solicitante_cliente": sol.solicitante_cliente,
        "vin": sol.vin,
        "ubicacion": sol.ubicacion,
        "tipo_servicio": sol.tipo_servicio,
        "no_parte": sol.no_parte,
        "descripcion": sol.descripcion,
        "cantidad": _num(sol.cantidad, 0),
        "alcance_servicio": sol.alcance_servicio,
        "proveedor_sugerido": sol.proveedor_sugerido,
        "precio": _num(sol.precio, 0),
        "moneda": sol.moneda,
        "total": _num(sol.total, 0),
        "fecha_requerida": sol.fecha_requerida.isoformat() if sol.fecha_requerida else None,
        "observaciones": sol.observaciones,
        "creado_por_nombre": sol.creado_por_nombre,
        "creado_por_email": sol.creado_por_email,
        "aprobador_nombre": sol.aprobador_nombre,
        "aprobador_email": sol.aprobador_email,
        "numero_sb": sol.numero_sb,
        "enviada_en": _iso(sol.enviada_en),
        "aprobada_en": _iso(sol.aprobada_en),
        "aprobacion_notificada_en": _iso(sol.aprobacion_notificada_en),
        "comprado_en": _iso(sol.comprado_en),
        "cerrado_en": _iso(sol.cerrado_en),
        "rechazada_en": _iso(sol.rechazada_en),
        "ultimo_recordatorio": _iso(sol.ultimo_recordatorio),
        "recordatorios_enviados": sol.recordatorios_enviados or 0,
        "creado_en": _iso(sol.creado_en),
        "actualizado_en": _iso(sol.actualizado_en),
        "dias": _dias(sol),
        "vencida": bool(pendiente and sol.enviada_en and (datetime.now() - sol.enviada_en) >= timedelta(days=DIAS_RECORDATORIO)),
        "adjuntos": len(sol.adjuntos or []),
        "comentarios": len(sol.comentarios or []),
    }


def _comentario(db: Session, sol: CotSolicitud, role: str, nombre: str, tipo: str, texto: str) -> CotComentario:
    item = CotComentario(
        id_solicitud=sol.id_solicitud,
        autor_rol=role,
        autor_nombre=nombre or role,
        tipo=tipo,
        texto=texto.strip(),
    )
    db.add(item)
    return item


def _registrar_correo(
    db: Session,
    sol: CotSolicitud,
    tipo: str,
    destinatario: str,
    asunto: str,
    cuerpo: str,
    estado: str,
    error: Optional[str],
) -> None:
    db.add(
        CotCorreo(
            id_solicitud=sol.id_solicitud,
            tipo=tipo,
            destinatario=destinatario or "",
            asunto=asunto,
            cuerpo=cuerpo,
            estado=estado,
            error=error,
        )
    )
    db.commit()


def _enviar_solicitud_correo(db: Session, sol: CotSolicitud) -> dict:
    destinatario = sol.aprobador_email or identidad("aprobador")["email"]
    asunto, texto, html = correo_solicitud(sol)
    estado, error = enviar(destinatario, asunto, texto, html)
    _registrar_correo(db, sol, "SOLICITUD", destinatario, asunto, texto, estado, error)
    return {"estado": estado, "error": error, "destinatario": destinatario}


def _enviar_decision_correo(db: Session, sol: CotSolicitud, aprobada: bool, comentario: Optional[str]) -> dict:
    destinatario = sol.creado_por_email or identidad("solicitante")["email"]
    asunto, texto, html = correo_decision(sol, aprobada, comentario)
    estado, error = enviar(destinatario, asunto, texto, html)
    _registrar_correo(db, sol, "APROBACION" if aprobada else "RECHAZO", destinatario, asunto, texto, estado, error)
    return {"estado": estado, "error": error, "destinatario": destinatario}


def procesar_recordatorios(db: Session) -> int:
    """Envia recordatorio a solicitudes pendientes de 2+ dias (cada 48 h)."""
    ahora = datetime.now()
    limite = ahora - timedelta(days=DIAS_RECORDATORIO)
    rows = db.scalars(
        select(CotSolicitud).where(
            CotSolicitud.estatus == "PENDIENTE",
            CotSolicitud.enviada_en.is_not(None),
            CotSolicitud.enviada_en <= limite,
            or_(
                CotSolicitud.ultimo_recordatorio.is_(None),
                CotSolicitud.ultimo_recordatorio <= ahora - timedelta(hours=HORAS_ENTRE_RECORDATORIOS),
            ),
        )
    ).all()

    enviados = 0
    for sol in rows:
        dias = max(DIAS_RECORDATORIO, int((ahora - sol.enviada_en).total_seconds() // 86400))
        destinatario = sol.aprobador_email or identidad("aprobador")["email"]
        asunto, texto, html = correo_recordatorio(sol, dias)
        estado, error = enviar(destinatario, asunto, texto, html)
        db.add(
            CotCorreo(
                id_solicitud=sol.id_solicitud,
                tipo="RECORDATORIO",
                destinatario=destinatario or "",
                asunto=asunto,
                cuerpo=texto,
                estado=estado,
                error=error,
            )
        )
        sol.recordatorios_enviados = (sol.recordatorios_enviados or 0) + 1
        sol.ultimo_recordatorio = ahora
        detalle = "Recordatorio enviado al aprobador" if estado != "ERROR" else f"Error al enviar recordatorio: {error}"
        _comentario(db, sol, "sistema", "Sistema", "SISTEMA", f"{detalle} ({dias} días pendiente).")
        db.commit()
        enviados += 1
    return enviados


# --------------------------------------------------------------------------
# Catalogos
# --------------------------------------------------------------------------
@router.get("/catalogos")
def catalogos(role: str = Depends(require_any), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(CotCatalogo).where(CotCatalogo.activo == 1).order_by(CotCatalogo.tipo, CotCatalogo.valor)
    ).all()
    data = {"cliente": [], "ubicacion": [], "tipo_servicio": [], "no_parte": [], "proveedor": []}
    for r in rows:
        data.setdefault(r.tipo, []).append({"id": r.id_catalogo, "valor": r.valor})
    return data


@router.post("/catalogos")
def agregar_catalogo(payload: CatalogoIn, role: str = Depends(require_any), db: Session = Depends(get_db)):
    valor = payload.valor.strip()
    if not valor:
        raise HTTPException(status_code=422, detail="Escribe un valor válido")
    existing = db.scalar(
        select(CotCatalogo).where(
            CotCatalogo.tipo == payload.tipo,
            func.lower(CotCatalogo.valor) == func.lower(valor),
        )
    )
    if existing:
        existing.valor = valor
        existing.activo = 1
        db.commit()
        db.refresh(existing)
        return {"id": existing.id_catalogo, "valor": existing.valor}
    item = CotCatalogo(tipo=payload.tipo, valor=valor, activo=1)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id_catalogo, "valor": item.valor}


# --------------------------------------------------------------------------
# Solicitudes (solicitante)
# --------------------------------------------------------------------------
@router.post("/solicitudes")
def crear_solicitud(
    payload: SolicitudIn,
    request: Request,
    role: str = Depends(require_solicitante),
    db: Session = Depends(get_db),
):
    quien = identidad(role)
    aprueba = identidad("aprobador")
    sol = CotSolicitud(
        # Valor temporal unico; el folio definitivo se calcula con el id.
        folio=f"TMP-{uuid.uuid4().hex[:12]}",
        estatus="BORRADOR",
        creado_por_rol=role,
        creado_por_nombre=quien["nombre"],
        creado_por_email=quien["email"] or None,
        aprobador_nombre=aprueba["nombre"],
        aprobador_email=aprueba["email"] or None,
        ip_origen=request.client.host if request.client else None,
    )
    _aplicar(sol, payload)
    db.add(sol)
    db.flush()
    sol.folio = _folio(sol.serie, sol.id_solicitud)
    _comentario(db, sol, role, quien["nombre"], "SISTEMA", "Borrador creado.")
    db.commit()
    db.refresh(sol)
    return _out(sol)


@router.put("/solicitudes/{id_solicitud}")
def actualizar_solicitud(
    id_solicitud: int,
    payload: SolicitudIn,
    role: str = Depends(require_solicitante),
    db: Session = Depends(get_db),
):
    sol = _get_sol(db, id_solicitud, role)
    if sol.estatus not in ("BORRADOR", "RECHAZADA"):
        raise HTTPException(status_code=409, detail="Solo se puede editar un borrador o una solicitud rechazada")
    _aplicar(sol, payload)
    db.commit()
    db.refresh(sol)
    return _out(sol)


@router.post("/solicitudes/{id_solicitud}/enviar")
def enviar_solicitud(
    id_solicitud: int,
    role: str = Depends(require_solicitante),
    db: Session = Depends(get_db),
):
    sol = _get_sol(db, id_solicitud, role)
    if sol.estatus not in ("BORRADOR", "RECHAZADA"):
        raise HTTPException(status_code=409, detail="Esta solicitud ya fue enviada")

    faltantes = []
    if not (sol.solicitante_cliente or "").strip():
        faltantes.append("Solicitante / Cliente")
    if not (sol.descripcion or "").strip():
        faltantes.append("Descripción")
    if _num(sol.cantidad, 0) <= 0:
        faltantes.append("Cantidad")
    if _num(sol.precio, 0) <= 0:
        faltantes.append("Precio")
    if faltantes:
        raise HTTPException(status_code=422, detail="Faltan campos obligatorios: " + ", ".join(faltantes))

    reenvio = sol.estatus == "RECHAZADA"
    sol.estatus = "PENDIENTE"
    sol.enviada_en = datetime.now()
    sol.aprobada_en = None
    sol.rechazada_en = None
    sol.numero_sb = None
    sol.recordatorios_enviados = 0
    sol.ultimo_recordatorio = None
    quien = identidad(role)
    aprueba = identidad("aprobador")
    # Refresca nombre/correo por si cambiaron en .env despues de crear el borrador.
    sol.creado_por_nombre = quien["nombre"] or sol.creado_por_nombre
    sol.creado_por_email = quien["email"] or sol.creado_por_email
    sol.aprobador_nombre = aprueba["nombre"] or sol.aprobador_nombre
    sol.aprobador_email = aprueba["email"] or sol.aprobador_email
    _comentario(
        db, sol, role, quien["nombre"], "SISTEMA",
        "Solicitud reenviada a aprobación." if reenvio else "Solicitud enviada a aprobación.",
    )
    db.commit()
    db.refresh(sol)
    correo = _enviar_solicitud_correo(db, sol)
    db.refresh(sol)
    return {**_out(sol), "correo": correo}


@router.post("/solicitudes/{id_solicitud}/comentarios")
def comentar(
    id_solicitud: int,
    payload: ComentarioIn,
    role: str = Depends(require_any),
    db: Session = Depends(get_db),
):
    sol = _get_sol(db, id_solicitud, role)
    quien = identidad(role)
    item = _comentario(db, sol, role, quien["nombre"], payload.tipo, payload.texto)
    db.commit()
    db.refresh(item)
    return {
        "id_comentario": item.id_comentario,
        "autor_rol": item.autor_rol,
        "autor_nombre": item.autor_nombre,
        "tipo": item.tipo,
        "texto": item.texto,
        "creado_en": _iso(item.creado_en),
    }


# --------------------------------------------------------------------------
# Revision / decision (aprobador)
# --------------------------------------------------------------------------
@router.post("/solicitudes/{id_solicitud}/aprobar")
def aprobar(
    id_solicitud: int,
    payload: DecisionIn,
    role: str = Depends(require_aprobador),
    db: Session = Depends(get_db),
):
    sol = _get_sol(db, id_solicitud, role)
    if sol.estatus != "PENDIENTE":
        raise HTTPException(status_code=409, detail="La solicitud no está pendiente de aprobación")
    comentario = (payload.comentario or "").strip() or "Solicitud aprobada."
    sol.estatus = "APROBADA"
    sol.aprobada_en = datetime.now()
    sol.numero_sb = (payload.numero_sb or "").strip() or None
    quien = identidad(role)
    _comentario(db, sol, role, quien["nombre"], "APROBACION", comentario)
    db.commit()
    db.refresh(sol)
    correo = _enviar_decision_correo(db, sol, True, comentario)
    # Paso extra: deja constancia de que el solicitante fue notificado.
    sol.aprobacion_notificada_en = datetime.now()
    _comentario(
        db, sol, "sistema", "Sistema", "SISTEMA",
        f"Aprobación notificada al solicitante ({correo.get('estado', 'SIMULADO')}).",
    )
    db.commit()
    db.refresh(sol)
    return {**_out(sol), "correo": correo}


@router.post("/solicitudes/{id_solicitud}/rechazar")
def rechazar(
    id_solicitud: int,
    payload: DecisionIn,
    role: str = Depends(require_aprobador),
    db: Session = Depends(get_db),
):
    sol = _get_sol(db, id_solicitud, role)
    if sol.estatus != "PENDIENTE":
        raise HTTPException(status_code=409, detail="La solicitud no está pendiente de aprobación")
    comentario = (payload.comentario or "").strip()
    if len(comentario) < 3:
        raise HTTPException(status_code=422, detail="Escribe el motivo del rechazo")
    sol.estatus = "RECHAZADA"
    sol.rechazada_en = datetime.now()
    quien = identidad(role)
    _comentario(db, sol, role, quien["nombre"], "RECHAZO", comentario)
    db.commit()
    db.refresh(sol)
    correo = _enviar_decision_correo(db, sol, False, comentario)
    db.refresh(sol)
    return {**_out(sol), "correo": correo}


@router.post("/solicitudes/{id_solicitud}/estatus")
def cambiar_estatus(
    id_solicitud: int,
    payload: CambioEstatusIn,
    role: str = Depends(require_solicitante),
    db: Session = Depends(get_db),
):
    """El solicitante marca la solicitud como COMPRADO y luego CERRADO."""
    sol = _get_sol(db, id_solicitud, role)
    if payload.estatus == "COMPRADO":
        if sol.estatus != "APROBADA":
            raise HTTPException(status_code=409, detail="Solo una solicitud aprobada puede marcarse como comprada")
        sol.estatus = "COMPRADO"
        sol.comprado_en = datetime.now()
        texto = "Solicitud marcada como comprada."
    else:
        if sol.estatus != "COMPRADO":
            raise HTTPException(status_code=409, detail="Solo una solicitud comprada puede cerrarse")
        sol.estatus = "CERRADO"
        sol.cerrado_en = datetime.now()
        texto = "Solicitud cerrada."

    quien = identidad(role)
    _comentario(db, sol, role, quien["nombre"], "SISTEMA", texto)
    db.commit()
    db.refresh(sol)
    return _out(sol)


# --------------------------------------------------------------------------
# Consulta
# --------------------------------------------------------------------------
@router.get("/solicitudes")
def listar_solicitudes(
    estatus: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = Query(default=300, le=1000),
    role: str = Depends(require_any),
    db: Session = Depends(get_db),
):
    stmt = select(CotSolicitud)
    if role == "aprobador":
        stmt = stmt.where(CotSolicitud.estatus != "BORRADOR")
    if estatus:
        estatus = estatus.upper()
        if estatus not in ("BORRADOR", "PENDIENTE", "APROBADA", "COMPRADO", "CERRADO", "RECHAZADA", "CANCELADA"):
            raise HTTPException(status_code=422, detail="Estatus no válido")
        stmt = stmt.where(CotSolicitud.estatus == estatus)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                CotSolicitud.folio.like(like),
                CotSolicitud.vin.like(like),
                CotSolicitud.descripcion.like(like),
                CotSolicitud.solicitante_cliente.like(like),
                CotSolicitud.no_parte.like(like),
                CotSolicitud.proveedor_sugerido.like(like),
            )
        )
    stmt = stmt.order_by(CotSolicitud.creado_en.desc()).limit(limit)
    return [_out(s) for s in db.scalars(stmt).all()]


@router.get("/solicitudes/{id_solicitud}")
def detalle_solicitud(
    id_solicitud: int,
    role: str = Depends(require_any),
    db: Session = Depends(get_db),
):
    sol = _get_sol(db, id_solicitud, role)
    data = _out(sol)
    data["comentarios_lista"] = [
        {
            "id_comentario": c.id_comentario,
            "autor_rol": c.autor_rol,
            "autor_nombre": c.autor_nombre,
            "tipo": c.tipo,
            "texto": c.texto,
            "creado_en": _iso(c.creado_en),
        }
        for c in sorted(sol.comentarios, key=lambda x: x.id_comentario)
    ]
    data["adjuntos_lista"] = [
        {
            "id_adjunto": a.id_adjunto,
            "nombre": a.nombre,
            "mime": a.mime,
            "tamano": a.tamano,
            "creado_en": _iso(a.creado_en),
        }
        for a in sorted(sol.adjuntos, key=lambda x: x.id_adjunto)
    ]
    correos = db.scalars(
        select(CotCorreo)
        .where(CotCorreo.id_solicitud == id_solicitud)
        .order_by(CotCorreo.creado_en.desc())
    ).all()
    data["correos_lista"] = [
        {
            "id_correo": c.id_correo,
            "tipo": c.tipo,
            "destinatario": c.destinatario,
            "asunto": c.asunto,
            "estado": c.estado,
            "error": c.error,
            "creado_en": _iso(c.creado_en),
        }
        for c in correos
    ]
    return data


@router.get("/resumen")
def resumen(role: str = Depends(require_any), db: Session = Depends(get_db)):
    stmt = select(CotSolicitud.estatus, func.count()).group_by(CotSolicitud.estatus)
    rows = dict(db.execute(stmt).all())
    if role == "aprobador":
        rows.pop("BORRADOR", None)
    total = sum(int(v) for v in rows.values())
    return {
        "total": total,
        "borradores": int(rows.get("BORRADOR", 0)),
        "pendientes": int(rows.get("PENDIENTE", 0)),
        "aprobadas": int(rows.get("APROBADA", 0)),
        "compradas": int(rows.get("COMPRADO", 0)),
        "cerradas": int(rows.get("CERRADO", 0)),
        "rechazadas": int(rows.get("RECHAZADA", 0)),
        "canceladas": int(rows.get("CANCELADA", 0)),
    }


@router.get("/indicadores")
def indicadores(role: str = Depends(require_aprobador), db: Session = Depends(get_db)):
    rows = db.scalars(select(CotSolicitud).where(CotSolicitud.estatus != "BORRADOR")).all()
    pendientes = [s for s in rows if s.estatus == "PENDIENTE"]
    aprobadas = [s for s in rows if s.estatus == "APROBADA"]
    compradas = [s for s in rows if s.estatus == "COMPRADO"]
    cerradas = [s for s in rows if s.estatus == "CERRADO"]
    aprobadas_historicas = [s for s in rows if s.estatus in ("APROBADA", "COMPRADO", "CERRADO")]
    rechazadas = [s for s in rows if s.estatus == "RECHAZADA"]
    decisiones = len(aprobadas_historicas) + len(rechazadas)

    tiempos = [
        (s.aprobada_en - s.enviada_en).total_seconds() / 3600
        for s in aprobadas_historicas
        if s.aprobada_en and s.enviada_en
    ]
    promedio_horas = round(sum(tiempos) / len(tiempos), 1) if tiempos else 0
    vencidas = [
        s for s in pendientes
        if s.enviada_en and (datetime.now() - s.enviada_en) >= timedelta(days=DIAS_RECORDATORIO)
    ]

    por_mes = {}
    for s in rows:
        clave = (s.creado_en or datetime.now()).strftime("%Y-%m")
        item = por_mes.setdefault(clave, {
            "mes": clave, "total": 0, "aprobadas": 0, "compradas": 0,
            "cerradas": 0, "rechazadas": 0,
        })
        item["total"] += 1
        if s.estatus == "APROBADA":
            item["aprobadas"] += 1
        elif s.estatus == "COMPRADO":
            item["compradas"] += 1
        elif s.estatus == "CERRADO":
            item["cerradas"] += 1
        elif s.estatus == "RECHAZADA":
            item["rechazadas"] += 1

    return {
        "total": len(rows),
        "pendientes": len(pendientes),
        "vencidas": len(vencidas),
        "aprobadas": len(aprobadas),
        "compradas": len(compradas),
        "cerradas": len(cerradas),
        "aprobadas_historicas": len(aprobadas_historicas),
        "rechazadas": len(rechazadas),
        "efectividad": round((len(aprobadas_historicas) / decisiones) * 100, 1) if decisiones else 0,
        "tiempo_promedio_horas": promedio_horas,
        "tiempo_promedio_dias": round(promedio_horas / 24, 1) if promedio_horas else 0,
        "recordatorios": sum((s.recordatorios_enviados or 0) for s in rows),
        "por_mes": [por_mes[k] for k in sorted(por_mes)][-6:],
    }


# --------------------------------------------------------------------------
# Adjuntos
# --------------------------------------------------------------------------
@router.post("/solicitudes/{id_solicitud}/adjuntos")
def subir_adjunto(
    id_solicitud: int,
    payload: AdjuntoIn,
    role: str = Depends(require_solicitante),
    db: Session = Depends(get_db),
):
    sol = _get_sol(db, id_solicitud, role)
    if sol.estatus not in ("BORRADOR", "RECHAZADA"):
        raise HTTPException(status_code=409, detail="Solo se pueden adjuntar archivos a un borrador o a una solicitud rechazada")

    raw = payload.contenido_base64.strip()
    if "," in raw and raw.lower().startswith("data:"):
        raw = raw.split(",", 1)[1]
    try:
        contenido = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail="El archivo no tiene un formato válido")
    if len(contenido) > MAX_ADJUNTO_BYTES:
        raise HTTPException(status_code=413, detail=f"El archivo supera el máximo de {MAX_ADJUNTO_BYTES // (1024*1024)} MB")

    item = CotAdjunto(
        id_solicitud=sol.id_solicitud,
        nombre=payload.nombre[:200],
        mime=payload.mime[:120],
        tamano=len(contenido),
        contenido=contenido,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {
        "id_adjunto": item.id_adjunto,
        "nombre": item.nombre,
        "mime": item.mime,
        "tamano": item.tamano,
        "creado_en": _iso(item.creado_en),
    }


@router.get("/adjuntos/{id_adjunto}")
def descargar_adjunto(
    id_adjunto: int,
    role: str = Depends(require_any),
    db: Session = Depends(get_db),
):
    item = db.get(CotAdjunto, id_adjunto)
    if not item:
        raise HTTPException(status_code=404, detail="Adjunto no encontrado")
    _get_sol(db, item.id_solicitud, role)
    filename = quote(item.nombre or "cotizacion")
    return Response(
        content=item.contenido,
        media_type=item.mime or "application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.delete("/adjuntos/{id_adjunto}")
def borrar_adjunto(
    id_adjunto: int,
    role: str = Depends(require_solicitante),
    db: Session = Depends(get_db),
):
    item = db.get(CotAdjunto, id_adjunto)
    if not item:
        raise HTTPException(status_code=404, detail="Adjunto no encontrado")
    sol = _get_sol(db, item.id_solicitud, role)
    if sol.estatus not in ("BORRADOR", "RECHAZADA"):
        raise HTTPException(status_code=409, detail="No se pueden quitar adjuntos de una solicitud enviada")
    db.delete(item)
    db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------
# Correos y recordatorios
# --------------------------------------------------------------------------
@router.get("/correos")
def listar_correos(
    id_solicitud: Optional[int] = None,
    limit: int = Query(default=100, le=500),
    role: str = Depends(require_aprobador),
    db: Session = Depends(get_db),
):
    stmt = select(CotCorreo).order_by(CotCorreo.creado_en.desc()).limit(limit)
    if id_solicitud:
        stmt = stmt.where(CotCorreo.id_solicitud == id_solicitud)
    return [
        {
            "id_correo": c.id_correo,
            "id_solicitud": c.id_solicitud,
            "tipo": c.tipo,
            "destinatario": c.destinatario,
            "asunto": c.asunto,
            "cuerpo": c.cuerpo,
            "estado": c.estado,
            "error": c.error,
            "creado_en": _iso(c.creado_en),
        }
        for c in db.scalars(stmt).all()
    ]


@router.post("/recordatorios/procesar")
def ejecutar_recordatorios(
    role: str = Depends(require_aprobador),
    db: Session = Depends(get_db),
):
    n = procesar_recordatorios(db)
    return {"ok": True, "recordatorios_enviados": n}
