# -*- coding: utf-8 -*-
"""
Segmentación de la demanda con K-Means (uso DESCRIPTIVO, real)
==============================================================
Agrupa los meses históricos según su nivel de consumo de raciones en 3 grupos
—Baja / Media / Alta demanda— usando K-Means. Aquí SÍ es válido agrupar por el
consumo: es un análisis DESCRIPTIVO del pasado (no un pronóstico), por lo que no
hay fuga de datos. Alimenta los indicadores del Dashboard:
  * "Comportamiento de la demanda" (indicadores)
  * "Períodos de alta y baja demanda" (segmentación K-Means)

Es de SOLO LECTURA y no crea tablas: se calcula al vuelo.
"""

import statistics


NIVELES = ["Baja", "Media", "Alta"]


def _completos(meses_valores) -> list:
    """Descarta el/los mes(es) finales incompletos (p. ej. el mes en curso): un
    mes cuyo total sea < 50% de la mediana se considera parcial y se recorta."""
    datos = [(m, int(v)) for m, v in meses_valores if v and v > 0]
    if len(datos) < 4:
        return datos
    med = statistics.median(v for _, v in datos)
    while len(datos) > 3 and datos[-1][1] < 0.5 * med:
        datos.pop()
    return datos


def segmentar_meses(meses_valores, k: int = 3) -> list:
    """Clasifica cada mes en Baja/Media/Alta demanda con K-Means.
    `meses_valores`: lista de (mes 'YYYY-MM', total_raciones). Devuelve una lista
    de dicts {mes, raciones, nivel}."""
    datos = _completos(meses_valores)
    if len(datos) < k:
        return [{"mes": m, "raciones": v, "nivel": "—"} for m, v in datos]

    from sklearn.cluster import KMeans
    import numpy as np

    X = np.array([[v] for _, v in datos], dtype=float)
    km = KMeans(n_clusters=k, random_state=2026, n_init=10).fit(X)
    # Ordena los clústeres por su centro para nombrarlos Baja<Media<Alta.
    orden = list(np.argsort(km.cluster_centers_.ravel()))
    nombres = NIVELES if k == 3 else [f"Nivel {i+1}" for i in range(k)]
    etiqueta = {c: nombres[i] for i, c in enumerate(orden)}
    return [{"mes": m, "raciones": v, "nivel": etiqueta[l]}
            for (m, v), l in zip(datos, km.labels_)]


def resumen_niveles(segmentado) -> list:
    """Agrega la segmentación por nivel: nº de meses, promedio y rango."""
    grupos = {}
    for r in segmentado:
        grupos.setdefault(r["nivel"], []).append(r["raciones"])
    out = []
    for niv in ["Alta", "Media", "Baja"]:
        if niv in grupos:
            v = grupos[niv]
            out.append({"nivel": niv, "meses": len(v),
                        "promedio": round(sum(v) / len(v)),
                        "min": min(v), "max": max(v)})
    return out


def indicadores(meses_valores) -> dict:
    """Indicadores del comportamiento de la demanda (mensual)."""
    datos = _completos(meses_valores)
    vals = [v for _, v in datos]
    if not vals:
        return {}
    prom = sum(vals) / len(vals)
    pico = max(datos, key=lambda x: x[1])
    bajo = min(datos, key=lambda x: x[1])
    # Tendencia: promedio de los últimos 6 meses vs. los 6 previos.
    ult = vals[-6:]
    prev = vals[-12:-6] if len(vals) >= 12 else (vals[:-6] or vals)
    base = sum(prev) / len(prev)
    tend = (sum(ult) / len(ult) - base) / base * 100 if base else 0.0
    cv = statistics.pstdev(vals) / prom * 100 if prom else 0.0
    return {
        "meses": len(vals),
        "promedio": round(prom),
        "pico_mes": pico[0], "pico_val": pico[1],
        "bajo_mes": bajo[0], "bajo_val": bajo[1],
        "tendencia_pct": round(tend, 1),
        "variabilidad_pct": round(cv, 1),
        "nivel_actual": None,  # lo completa quien tenga la segmentación
    }
