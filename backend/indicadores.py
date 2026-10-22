"""Indicadores para el panel: Fatiga y Seguridad.

Solo lectura. No modifica fatiga_* ni sst_*.
Rango por defecto: ultimos 30 dias.
"""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from .auth import require_reports
from .db import get_db
from .models import (
    FatigaPregunta,
    FatigaRespuesta,
    FatigaTest,
    SstAuditoria,
    SstPregunta,
    SstRespuesta,
)

router = APIRouter(prefix="/api/indicadores", tags=["Indicadores"])


def _rango(desde: Optional[date], hasta: Optional[date]):
    if not hasta:
        hasta = date.today()
    if not desde:
        desde = hasta - timedelta(days=30)
    if desde > hasta:
        desde, hasta = hasta, desde
    return desde, hasta


def _bucket():
    return {"total": 0, "verde": 0, "amarillo": 0, "rojo": 0, "criticas": 0}


def _add_bucket(d: dict, key: str, test: FatigaTest):
    b = d.setdefault(key or "Sin dato", _bucket())
    b["total"] += 1
    b[test.semaforo.lower()] += 1
    b["criticas"] += int(test.critica_con_2pts or 0)


def _finish(d: dict):
    out = []
    for key, b in d.items():
        riesgo = b["amarillo"] + b["rojo"]
        out.append({
            **b,
            "nombre": key,
            "riesgo": riesgo,
            "riesgo_pct": round((riesgo / b["total"]) * 100) if b["total"] else 0,
        })
    out.sort(key=lambda x: (-x["riesgo"], -x["total"], x["nombre"]))
    return out


@router.get("/fatiga", dependencies=[Depends(require_reports)])
def indicadores_fatiga(
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    db: Session = Depends(get_db),
):
    desde, hasta = _rango(desde, hasta)
    tests = db.scalars(
        select(FatigaTest).where(FatigaTest.fecha >= desde, FatigaTest.fecha <= hasta)
    ).all()

    total = len(tests)
    verde = sum(1 for t in tests if t.semaforo == "VERDE")
    amarillo = sum(1 for t in tests if t.semaforo == "AMARILLO")
    rojo = sum(1 for t in tests if t.semaforo == "ROJO")
    criticas = sum(1 for t in tests if t.critica_con_2pts)

    por_depto: dict = {}
    por_turno: dict = {}
    for t in tests:
        _add_bucket(por_depto, (t.departamento or "Sin departamento"), t)
        _add_bucket(por_turno, (t.turno or "Sin turno"), t)

    ids = [t.id_test for t in tests]
    preguntas = {
        p.id_pregunta: p for p in db.scalars(select(FatigaPregunta)).all()
    }
    por_pregunta = []
    if ids:
        rows = db.execute(
            select(
                FatigaRespuesta.id_pregunta,
                func.count(FatigaRespuesta.id_respuesta),
                func.coalesce(func.sum(FatigaRespuesta.valor), 0),
                func.coalesce(
                    func.sum(case((FatigaRespuesta.valor == 2, 1), else_=0)), 0
                ),
            )
            .where(FatigaRespuesta.id_test.in_(ids))
            .group_by(FatigaRespuesta.id_pregunta)
        ).all()
        for pid, n, suma, dos in rows:
            p = preguntas.get(pid)
            por_pregunta.append({
                "id_pregunta": pid,
                "texto": p.texto if p else "",
                "critica": bool(p.critica) if p else False,
                "respuestas": int(n or 0),
                "promedio": round((float(suma or 0) / int(n)), 2) if n else 0,
                "dos_puntos": int(dos or 0),
            })
        por_pregunta.sort(key=lambda x: (-x["promedio"], -x["dos_puntos"], x["id_pregunta"]))

    return {
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "total": total,
        "verde": verde,
        "amarillo": amarillo,
        "rojo": rojo,
        "criticas": criticas,
        "riesgo_pct": round(((amarillo + rojo) / total) * 100) if total else 0,
        "por_departamento": _finish(por_depto),
        "por_turno": _finish(por_turno),
        "por_pregunta": por_pregunta,
    }


@router.get("/sst", dependencies=[Depends(require_reports)])
def indicadores_sst(
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    db: Session = Depends(get_db),
):
    desde, hasta = _rango(desde, hasta)
    auditorias = db.scalars(
        select(SstAuditoria).where(
            SstAuditoria.fecha >= desde, SstAuditoria.fecha <= hasta
        )
    ).all()

    total = len(auditorias)
    seguras = sum(a.seguras for a in auditorias)
    inseguras = sum(a.inseguras for a in auditorias)
    con_hallazgos = sum(1 for a in auditorias if a.inseguras > 0)

    def agg(getter):
        d = {}
        for a in auditorias:
            key = getter(a) or "Sin dato"
            b = d.setdefault(key, {"nombre": key, "total": 0, "seguras": 0, "inseguras": 0, "con_hallazgos": 0})
            b["total"] += 1
            b["seguras"] += a.seguras
            b["inseguras"] += a.inseguras
            b["con_hallazgos"] += 1 if a.inseguras > 0 else 0
        out = list(d.values())
        for b in out:
            b["pct"] = round((b["seguras"] / (b["total"] * 18)) * 100) if b["total"] else 0
        out.sort(key=lambda x: (-x["inseguras"], -x["total"], x["nombre"]))
        return out

    por_area = agg(lambda a: a.area)
    por_departamento = agg(lambda a: a.departamento)
    por_auditor = agg(lambda a: a.auditor)

    ids = [a.id_auditoria for a in auditorias]
    preguntas = {p.id_pregunta: p.texto for p in db.scalars(select(SstPregunta)).all()}
    por_conducta = []
    if ids:
        rows = db.execute(
            select(SstRespuesta.n, func.count(SstRespuesta.id_respuesta))
            .where(
                SstRespuesta.id_auditoria.in_(ids),
                SstRespuesta.estado == "INSEGURO",
            )
            .group_by(SstRespuesta.n)
        ).all()
        for n, count in rows:
            por_conducta.append({
                "n": int(n),
                "texto": preguntas.get(n, ""),
                "inseguras": int(count or 0),
            })
        por_conducta.sort(key=lambda x: (-x["inseguras"], x["n"]))

    return {
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "total": total,
        "seguras": seguras,
        "inseguras": inseguras,
        "porcentaje": round((seguras / (total * 18)) * 100) if total else 0,
        "con_hallazgos": con_hallazgos,
        "por_area": por_area,
        "por_departamento": por_departamento,
        "por_auditor": por_auditor,
        "por_conducta": por_conducta,
    }
