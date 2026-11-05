"""Esquemas Pydantic del modulo CAR."""
from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class CarAreaOut(BaseModel):
    id: int
    nombre: str


class CarZonaOut(BaseModel):
    id_zona: int
    nombre: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    radio_m: int = 300
    areas: List[CarAreaOut] = Field(default_factory=list)


class CarCatalogosOut(BaseModel):
    areas: List[CarAreaOut]
    zonas: List[CarZonaOut] = Field(default_factory=list)


class CarZonaIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=60)
    lat: Optional[float] = None
    lng: Optional[float] = None
    radio_m: int = Field(default=300, ge=10, le=50000)


class CarZonaUpdate(BaseModel):
    lat: Optional[float] = None
    lng: Optional[float] = None
    radio_m: Optional[int] = Field(default=None, ge=10, le=50000)


class CarAreaIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    id_zona: Optional[int] = None


class CarEmpleadoOut(BaseModel):
    id_usuario: int
    nombre_completo: str
    num_empleado: Optional[int] = None
    departamento: Optional[str] = None
    puesto: Optional[str] = None
    empresa: Optional[str] = None
    foto_url: Optional[str] = None
    fuente: str = "fatiga"


class CarEvidenciaOut(BaseModel):
    id_evidencia: int
    tipo: str
    nombre: str
    mime: str
    tamano: int
    url: str


class CarTarjetaIn(BaseModel):
    fecha: date
    id_usuario: int = Field(gt=0)
    id_zona: Optional[int] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    origen_geo: Optional[str] = None
    area: str = Field(min_length=2, max_length=120)
    tipo: Literal["ACTO_SEGURO", "CONDICION_INSEGURA", "ACTO_INSEGURO", "FALLA_ADMINISTRATIVA"]
    descripcion: str = Field(min_length=10, max_length=2000)
    controlado: Literal["SI", "NO"]
    clasificacion: Literal["AMARILLO", "ROJO"]
    acciones_inmediatas: Optional[str] = Field(default=None, max_length=1500)
    acciones_definitivas: Optional[str] = Field(default=None, max_length=1500)
    fecha_compromiso: Optional[date] = None
    firma_emisor: str = Field(min_length=20, max_length=500000)
    evidencias: List[int] = Field(default_factory=list, max_length=20)


class CarCierreIn(BaseModel):
    responsable: str = Field(min_length=2, max_length=120)
    area_responsable: str = Field(min_length=2, max_length=120)
    firma_responsable: str = Field(min_length=20, max_length=500000)
    comentario_cierre: str = Field(min_length=5, max_length=4000)
    fecha_cierre: Optional[date] = None
    revision: bool = True
    evidencias: List[int] = Field(default_factory=list, max_length=20)


class CarListaOut(BaseModel):
    id_tarjeta: int
    folio: str
    fecha: date
    observador: str
    num_empleado: Optional[int] = None
    area: str
    zona: Optional[str] = None
    tipo: str
    clasificacion: str
    controlado: str
    estado: str
    evidencias: int = 0
    fecha_cierre: Optional[date] = None
    responsable: Optional[str] = None
    creado_en: Optional[str] = None


class CarDetalleOut(CarListaOut):
    descripcion: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    origen_geo: Optional[str] = None
    acciones_inmediatas: Optional[str] = None
    acciones_definitivas: Optional[str] = None
    fecha_compromiso: Optional[date] = None
    firma_emisor: str
    firma_responsable: Optional[str] = None
    area_responsable: Optional[str] = None
    comentario_cierre: Optional[str] = None
    revision: bool = False
    cerrado_en: Optional[str] = None
    lista_evidencias: List[CarEvidenciaOut] = Field(default_factory=list)
