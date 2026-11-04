"""Modelos del modulo CAR · Tarjeta de control y administración de riesgos."""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..tz import ahora
from .db import Base

# En MySQL son BIGINT/SMALLINT AUTO_INCREMENT; en SQLite deben ser INTEGER
# para que el PRIMARY KEY autoincremente.
BigIntPK = BigInteger().with_variant(Integer, "sqlite")
SmallIntPK = SmallInteger().with_variant(Integer, "sqlite")


class CarArea(Base):
    """Áreas / departamentos del observador, administrados desde el panel."""

    __tablename__ = "car_areas"

    id_area: Mapped[int] = mapped_column(SmallIntPK, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True)
    activo: Mapped[int] = mapped_column(SmallInteger, default=1)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class CarTarjeta(Base):
    __tablename__ = "car_tarjetas"

    id_tarjeta: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    folio: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    fecha: Mapped[date] = mapped_column(Date, index=True)
    id_usuario: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    observador: Mapped[str] = mapped_column(String(120), index=True)
    num_empleado: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    area: Mapped[str] = mapped_column(String(120), index=True)
    tipo: Mapped[str] = mapped_column(String(30))
    descripcion: Mapped[str] = mapped_column(Text)
    controlado: Mapped[str] = mapped_column(String(2))
    clasificacion: Mapped[str] = mapped_column(String(10), index=True)
    acciones_inmediatas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    acciones_definitivas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fecha_compromiso: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    firma_emisor: Mapped[str] = mapped_column(Text)

    # Parte 5: la completa únicamente el administrador desde el panel.
    estado: Mapped[str] = mapped_column(String(12), default="PENDIENTE", index=True)
    responsable: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    area_responsable: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    firma_responsable: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    comentario_cierre: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    revision: Mapped[int] = mapped_column(SmallInteger, default=0)
    fecha_cierre: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    cerrado_en: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cerrado_por: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)

    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    ip_origen: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    evidencias: Mapped[list["CarEvidencia"]] = relationship(
        back_populates="tarjeta", cascade="all, delete-orphan"
    )


class CarEvidencia(Base):
    """Archivo (foto o video) ligado a una tarjeta CAR."""

    __tablename__ = "car_evidencias"

    id_evidencia: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    id_tarjeta: Mapped[Optional[int]] = mapped_column(
        BigIntPK, ForeignKey("car_tarjetas.id_tarjeta", ondelete="CASCADE"), nullable=True, index=True
    )
    tipo: Mapped[str] = mapped_column(String(10))  # FOTO | VIDEO
    nombre: Mapped[str] = mapped_column(String(255))
    mime: Mapped[str] = mapped_column(String(100))
    tamano: Mapped[int] = mapped_column(Integer)
    archivo: Mapped[str] = mapped_column(String(80), unique=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)

    tarjeta: Mapped[Optional["CarTarjeta"]] = relationship(back_populates="evidencias")
