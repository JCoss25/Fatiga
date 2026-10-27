"""Esquemas Pydantic (entrada/salida de la API)."""
from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


class LoginOut(BaseModel):
    ok: bool
    role: str
    nombre: str
    email: str


class CatalogoItemOut(BaseModel):
    id: int
    valor: str


class CatalogosOut(BaseModel):
    cliente: List[CatalogoItemOut] = []
    ubicacion: List[CatalogoItemOut] = []
    tipo_servicio: List[CatalogoItemOut] = []
    no_parte: List[CatalogoItemOut] = []
    proveedor: List[CatalogoItemOut] = []


class CatalogoIn(BaseModel):
    tipo: str = Field(pattern="^(cliente|ubicacion|tipo_servicio|no_parte|proveedor)$")
    valor: str = Field(min_length=1, max_length=160)


class SolicitudIn(BaseModel):
    """Todos los campos del formato Orden de Reparacion TOT."""

    serie: str = Field(default="LC", pattern="^(LC|NDVC)$")
    fecha_solicitud: Optional[date] = None
    solicitante_cliente: str = Field(default="", max_length=160)
    vin: str = Field(default="", max_length=30)
    ubicacion: str = Field(default="", max_length=120)
    tipo_servicio: str = Field(default="", max_length=120)
    no_parte: str = Field(default="", max_length=120)
    descripcion: str = Field(default="", max_length=4000)
    cantidad: float = Field(default=1, ge=0, le=999999)
    alcance_servicio: str = Field(default="", max_length=4000)
    proveedor_sugerido: str = Field(default="", max_length=160)
    precio: float = Field(default=0, ge=0, le=999999999)
    moneda: str = Field(default="MXN", pattern="^(MXN|USD|EUR)$")
    fecha_requerida: Optional[date] = None
    observaciones: str = Field(default="", max_length=4000)
    datos: dict = Field(default_factory=dict)


class DecisionIn(BaseModel):
    comentario: Optional[str] = Field(default=None, max_length=2000)
    numero_sb: Optional[str] = Field(default=None, max_length=60)


class ComentarioIn(BaseModel):
    texto: str = Field(min_length=1, max_length=2000)
    tipo: str = Field(default="COMENTARIO", pattern="^(COMENTARIO|REVISION)$")


class AdjuntoIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    mime: str = Field(default="application/octet-stream", max_length=120)
    contenido_base64: str = Field(min_length=4, max_length=12_000_000)


class ComentarioOut(BaseModel):
    id_comentario: int
    autor_rol: str
    autor_nombre: str
    tipo: str
    texto: str
    creado_en: Optional[str]


class AdjuntoOut(BaseModel):
    id_adjunto: int
    nombre: str
    mime: str
    tamano: int
    creado_en: Optional[str]


class CorreoOut(BaseModel):
    id_correo: int
    id_solicitud: Optional[int]
    tipo: str
    destinatario: str
    asunto: str
    cuerpo: str
    estado: str
    error: Optional[str]
    creado_en: Optional[str]
