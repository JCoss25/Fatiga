"""Esquemas Pydantic (entrada/salida de la API)."""
from datetime import date, time
from typing import List, Optional

from pydantic import BaseModel, Field


class PreguntaOut(BaseModel):
    id_pregunta: int
    seccion: str
    orden: int
    texto: str
    critica: bool
    opciones: List[str]


class RespuestaIn(BaseModel):
    id_pregunta: int = Field(ge=1, le=10)
    valor: int = Field(ge=0, le=2)


class TestIn(BaseModel):
    id_usuario: Optional[int] = None
    num_empleado: Optional[int] = None
    nombre_completo: str = Field(min_length=2, max_length=100)
    puesto: Optional[str] = None
    departamento: Optional[str] = None
    empresa: Optional[str] = None
    turno: Optional[str] = None
    hora_entrada: Optional[str] = None  # "HH:MM"
    fecha: Optional[date] = None
    respuestas: List[RespuestaIn]
    accion_tomada: Optional[str] = None
    observaciones: Optional[str] = None
    firma_trabajador: Optional[str] = None
    firma_imagen: Optional[str] = None
    validador_nombre: Optional[str] = None


class RespuestaOut(BaseModel):
    id_pregunta: int
    valor: int


class TestOut(BaseModel):
    id_test: int
    id_usuario: Optional[int]
    num_empleado: Optional[int]
    nombre_completo: str
    puesto: Optional[str]
    departamento: Optional[str]
    empresa: Optional[str]
    turno: Optional[str]
    hora_entrada: Optional[time]
    fecha: date
    puntaje_total: int
    semaforo: str
    critica_con_2pts: bool
    jornada_extra: str
    accion_tomada: Optional[str]
    observaciones: Optional[str]
    firma_trabajador: Optional[str]
    validador_nombre: Optional[str]
    creado_en: Optional[str]


class TestDetalleOut(TestOut):
    respuestas: List[RespuestaOut] = []
    criticas_con_2pts: List[int] = []
    recomendacion: str = ""
    firma_imagen: Optional[str] = None
