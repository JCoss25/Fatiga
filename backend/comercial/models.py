"""Modelos SQLAlchemy del modulo de Cotizacion de danos.

Tablas nuevas con prefijo `cot_`; no se modifica ninguna tabla existente.
"""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    JSON, BigInteger, Date, DateTime, Enum, ForeignKey, Integer, LargeBinary,
    Numeric, SmallInteger, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

# En MySQL es BIGINT AUTO_INCREMENT; en SQLite debe ser INTEGER para autoincrementar.
BigIntPK = BigInteger().with_variant(Integer, "sqlite")

ESTATUS = ("BORRADOR", "PENDIENTE", "APROBADA", "RECHAZADA", "CANCELADA")
TIPOS_COMENTARIO = ("COMENTARIO", "REVISION", "APROBACION", "RECHAZO", "SISTEMA")
TIPOS_CORREO = ("SOLICITUD", "RECORDATORIO", "APROBACION", "RECHAZO")


class CotSolicitud(Base):
    """Orden de Reparacion TOT (solicitud de cotizacion de danos)."""

    __tablename__ = "cot_solicitudes"

    id_solicitud: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    folio: Mapped[str] = mapped_column(String(30), unique=True)
    serie: Mapped[str] = mapped_column(String(10), default="LC")
    estatus: Mapped[str] = mapped_column(Enum(*ESTATUS), default="BORRADOR")

    # --- Campos del formato (Orden de Reparacion TOT) ---
    fecha_solicitud: Mapped[date] = mapped_column(Date, default=date.today)
    solicitante_cliente: Mapped[str] = mapped_column(String(160), default="")
    vin: Mapped[str] = mapped_column(String(30), default="")
    ubicacion: Mapped[str] = mapped_column(String(120), default="")
    tipo_servicio: Mapped[str] = mapped_column(String(120), default="")
    no_parte: Mapped[str] = mapped_column(String(120), default="")
    descripcion: Mapped[str] = mapped_column(Text, default="")
    cantidad: Mapped[float] = mapped_column(Numeric(12, 2), default=1)
    alcance_servicio: Mapped[str] = mapped_column(Text, default="")
    proveedor_sugerido: Mapped[str] = mapped_column(String(160), default="")
    precio: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    moneda: Mapped[str] = mapped_column(String(3), default="MXN")
    total: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    fecha_requerida: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    observaciones: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Copia flexible de todos los campos (para crecer sin migrar cada vez).
    datos: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # --- Identidad y aprobacion ---
    creado_por_rol: Mapped[str] = mapped_column(String(20), default="solicitante")
    creado_por_nombre: Mapped[str] = mapped_column(String(120), default="")
    creado_por_email: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    aprobador_nombre: Mapped[str] = mapped_column(String(120), default="")
    aprobador_email: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    numero_sb: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)

    # --- Fechas de control / recordatorios ---
    enviada_en: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    aprobada_en: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    rechazada_en: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ultimo_recordatorio: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    recordatorios_enviados: Mapped[int] = mapped_column(Integer, default=0)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
    ip_origen: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    comentarios: Mapped[list["CotComentario"]] = relationship(
        back_populates="solicitud", cascade="all, delete-orphan"
    )
    adjuntos: Mapped[list["CotAdjunto"]] = relationship(
        back_populates="solicitud", cascade="all, delete-orphan"
    )


class CotComentario(Base):
    __tablename__ = "cot_comentarios"

    id_comentario: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    id_solicitud: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("cot_solicitudes.id_solicitud", ondelete="CASCADE")
    )
    autor_rol: Mapped[str] = mapped_column(String(20))
    autor_nombre: Mapped[str] = mapped_column(String(120))
    tipo: Mapped[str] = mapped_column(Enum(*TIPOS_COMENTARIO), default="COMENTARIO")
    texto: Mapped[str] = mapped_column(Text)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    solicitud: Mapped["CotSolicitud"] = relationship(back_populates="comentarios")


class CotAdjunto(Base):
    """Cotizacion adjunta. Se guarda en la BD para sobrevivir reinicios."""

    __tablename__ = "cot_adjuntos"

    id_adjunto: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    id_solicitud: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("cot_solicitudes.id_solicitud", ondelete="CASCADE")
    )
    nombre: Mapped[str] = mapped_column(String(200))
    mime: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    tamano: Mapped[int] = mapped_column(Integer, default=0)
    contenido: Mapped[bytes] = mapped_column(LargeBinary)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    solicitud: Mapped["CotSolicitud"] = relationship(back_populates="adjuntos")


class CotCorreo(Base):
    """Bitacora de correos. En modo simulado tambien se guarda aqui."""

    __tablename__ = "cot_correos"

    id_correo: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    id_solicitud: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("cot_solicitudes.id_solicitud", ondelete="SET NULL"), nullable=True
    )
    tipo: Mapped[str] = mapped_column(Enum(*TIPOS_CORREO), default="SOLICITUD")
    destinatario: Mapped[str] = mapped_column(String(200), default="")
    asunto: Mapped[str] = mapped_column(String(255), default="")
    cuerpo: Mapped[str] = mapped_column(Text, default="")
    estado: Mapped[str] = mapped_column(Enum("SIMULADO", "ENVIADO", "ERROR"), default="SIMULADO")
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class CotCatalogo(Base):
    """Catalogos editables: cliente, ubicacion, tipo de servicio, no. de parte, proveedor."""

    __tablename__ = "cot_catalogos"
    __table_args__ = (UniqueConstraint("tipo", "valor", name="uq_cot_catalogo"),)

    id_catalogo: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tipo: Mapped[str] = mapped_column(String(30))
    valor: Mapped[str] = mapped_column(String(160))
    activo: Mapped[int] = mapped_column(SmallInteger, default=1)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


