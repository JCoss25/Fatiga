"""Reglas de negocio del test de fatiga (puntaje, semaforo, jornada extra)."""

# Umbrales del semaforo (tomados del documento).
UMBRAL_VERDE_MAX = 5      # 0 - 5
UMBRAL_AMARILLO_MAX = 10  # 6 - 10
# Rojo: 11 - 20

RECOMENDACIONES = {
    "VERDE": (
        "Fatiga baja. Puede realizar su jornada normal con las actividades "
        "habituales."
    ),
    "AMARILLO": (
        "Fatiga moderada. Jornada normal con supervisión cercana, pausas "
        "activas y de hidratación; evitar tareas de mayor riesgo si es posible."
    ),
    "ROJO": (
        "Fatiga alta. No iniciar maniobras ni conducción de unidades. Avisar al "
        "supervisor y a salud ocupacional para valoración y, de ser necesario, "
        "reasignar o descansar."
    ),
}


def semaforo_de(puntaje: int) -> str:
    if puntaje <= UMBRAL_VERDE_MAX:
        return "VERDE"
    if puntaje <= UMBRAL_AMARILLO_MAX:
        return "AMARILLO"
    return "ROJO"


def calcular(respuestas: dict[int, int], criticas: set[int]) -> dict:
    """
    respuestas: {id_pregunta: valor(0/1/2)}
    criticas:   conjunto de ids de preguntas criticas.

    Reglas:
      - Puntaje total = suma de las 10 respuestas (0-20).
      - Semaforo: Verde 0-5 / Amarillo 6-10 / Rojo 11-20.
      - Pregunta critica con 2 puntos -> NO se permite jornada extra,
        aunque el puntaje total sea Verde.
    """
    total = sum(int(v) for v in respuestas.values())
    semaforo = semaforo_de(total)

    criticas_con_2 = sorted(p for p in criticas if respuestas.get(p) == 2)
    critica_flag = bool(criticas_con_2)

    puede_extra = (semaforo == "VERDE") and not critica_flag

    return {
        "puntaje_total": total,
        "semaforo": semaforo,
        "critica_con_2pts": critica_flag,
        "criticas_con_2pts": criticas_con_2,
        "jornada_extra": "PUEDE" if puede_extra else "NO_DEBE",
        "recomendacion": RECOMENDACIONES[semaforo],
    }
