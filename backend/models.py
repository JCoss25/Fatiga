"""Modelos SQLAlchemy: tabla existente `usuarios` (solo lectura) + tablas fatiga_*."""
from datetime import date, datetime, time
from typing import Optional

from sqlalchemy import (
    BigInteger, Date, DateTime, Enum, ForeignKey, Integer, LargeBinary,
    SmallInteger, String, Text, Time,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base
from .tz import ahora


class Usuario(Base):
    """Tabla existente en la base kogn1v1s (NO la crea esta app, solo la lee)."""

    __tablename__ = "usuarios"

    id_usuario: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre_completo: Mapped[str] = mapped_column(String(70))
    num_empleado: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    face_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    code_externo: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    estatus: Mapped[int] = mapped_column(SmallInteger, default=1)
    puesto: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    departamento: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    id_estatus: Mapped[int] = mapped_column(Integer, default=1)
    interno_externo: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    img_empleado: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    empresa: Mapped[Optional[str]] = mapped_column(String(70), nullable=True)


class FatigaPregunta(Base):
    __tablename__ = "fatiga_preguntas"

    id_pregunta: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    seccion: Mapped[str] = mapped_column(String(40))
    orden: Mapped[int] = mapped_column(SmallInteger)
    texto: Mapped[str] = mapped_column(String(255))
    critica: Mapped[int] = mapped_column(SmallInteger, default=0)
    opcion_0: Mapped[str] = mapped_column(String(140))
    opcion_1: Mapped[str] = mapped_column(String(140))
    opcion_2: Mapped[str] = mapped_column(String(140))


class FatigaTest(Base):
    __tablename__ = "fatiga_tests"

    id_test: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    id_usuario: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    num_empleado: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    nombre_completo: Mapped[str] = mapped_column(String(100))
    puesto: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    departamento: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    empresa: Mapped[Optional[str]] = mapped_column(String(70), nullable=True)
    turno: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    hora_entrada: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    fecha: Mapped[date] = mapped_column(Date)
    puntaje_total: Mapped[int] = mapped_column(SmallInteger)
    semaforo: Mapped[str] = mapped_column(Enum("VERDE", "AMARILLO", "ROJO"))
    critica_con_2pts: Mapped[int] = mapped_column(SmallInteger, default=0)
    jornada_extra: Mapped[str] = mapped_column(Enum("PUEDE", "NO_DEBE"))
    accion_tomada: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    observaciones: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    firma_trabajador: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    validador_nombre: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    ip_origen: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    respuestas: Mapped[list["FatigaRespuesta"]] = relationship(
        back_populates="test", cascade="all, delete-orphan"
    )


class FatigaRespuesta(Base):
    __tablename__ = "fatiga_respuestas"

    id_respuesta: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    id_test: Mapped[int] = mapped_column(BigInteger, ForeignKey("fatiga_tests.id_test"))
    id_pregunta: Mapped[int] = mapped_column(SmallInteger)
    valor: Mapped[int] = mapped_column(SmallInteger)

    test: Mapped["FatigaTest"] = relationship(back_populates="respuestas")


class FatigaFirma(Base):
    """Imagen de la firma dibujada (PNG en base64) asociada a un test."""

    __tablename__ = "fatiga_firmas"

    id_test: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    firma_imagen: Mapped[str] = mapped_column(Text)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)


# --------------------------------------------------------------------------
# Check list de seguridad basada en comportamiento (REG-SST-25)
# Modulo independiente: no modifica fatiga_*.
# --------------------------------------------------------------------------
class SstPregunta(Base):
    __tablename__ = "sst_preguntas"

    id_pregunta: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    orden: Mapped[int] = mapped_column(SmallInteger)
    texto: Mapped[str] = mapped_column(String(255))


class SstAuditoria(Base):
    __tablename__ = "sst_auditorias"

    id_auditoria: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fecha: Mapped[date] = mapped_column(Date)
    area: Mapped[str] = mapped_column(String(100))
    departamento: Mapped[str] = mapped_column(String(100))
    auditado: Mapped[str] = mapped_column(String(120))
    auditor: Mapped[str] = mapped_column(String(120))
    comentarios: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    seguras: Mapped[int] = mapped_column(SmallInteger)
    inseguras: Mapped[int] = mapped_column(SmallInteger)
    porcentaje: Mapped[int] = mapped_column(SmallInteger)
    firma_trabajador: Mapped[str] = mapped_column(Text)
    firma_auditor: Mapped[str] = mapped_column(Text)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    ip_origen: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    respuestas: Mapped[list["SstRespuesta"]] = relationship(
        back_populates="auditoria", cascade="all, delete-orphan"
    )


class SstRespuesta(Base):
    __tablename__ = "sst_respuestas"

    id_respuesta: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    id_auditoria: Mapped[int] = mapped_column(BigInteger, ForeignKey("sst_auditorias.id_auditoria"))
    n: Mapped[int] = mapped_column(SmallInteger)
    estado: Mapped[str] = mapped_column(Enum("SEGURO", "INSEGURO"))
    observacion: Mapped[Optional[str]] = mapped_column(String(400), nullable=True)

    auditoria: Mapped["SstAuditoria"] = relationship(back_populates="respuestas")


class SstAuditor(Base):
    """Catalogo de auditores que el administrador agrega desde el panel."""

    __tablename__ = "sst_auditores"

    id_auditor: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True)
    activo: Mapped[int] = mapped_column(SmallInteger, default=1)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class SstArea(Base):
    """Catalogo de areas que el administrador agrega desde el panel."""

    __tablename__ = "sst_areas"

    id_area: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True)
    activo: Mapped[int] = mapped_column(SmallInteger, default=1)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)

