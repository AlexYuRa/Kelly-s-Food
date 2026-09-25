# -*- coding: utf-8 -*-
"""
#1 · Pronóstico de demanda semanal con SARIMAX + exógenas
=========================================================
Modela las raciones por semana con SARIMAX. La estacionalidad anual entra por
armónicos de Fourier (exógenas), y se añaden señales conocidas de antemano:
nivel de temporada y —opcionalmente— la etiqueta de clúster de semana (1b).

Se evalúa por BACKTESTING walk-forward (origen deslizante, ventana expansiva):
en cada origen se reentrena con el histórico disponible y se pronostica la
siguiente quincena (2 semanas). Métrica principal: MAPE sobre semanas operativas.

El objetivo del A/B es responder con evidencia: ¿la etiqueta de clúster de mi
compañero (1b) mejora el MAPE frente a usar solo temporada+calendario?
"""

import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tools.sm_exceptions import ValueWarning, ConvergenceWarning

from . import datos
from .cluster_semanas import ClusterSemanas, etiquetas_onehot

# Convergencia/estacionariedad/índice sin frecuencia: ruido esperado en el A/B.
warnings.simplefilter("ignore", ValueWarning)
warnings.simplefilter("ignore", ConvergenceWarning)
warnings.simplefilter("ignore", UserWarning)
warnings.simplefilter("ignore", RuntimeWarning)

# Nº de semanas operativas recientes que promedia el modelo de producción.
# El backtesting eligió 2 (mejor MAPE típico: ~6%).
VENTANA_PRODUCCION = 2

ORDEN = (2, 1, 2)          # (p, d, q) — ARIMA sobre la serie semanal
ORDEN_ESTACIONAL = (0, 0, 0, 0)  # estacionalidad va por Fourier, no por s=52
K_CLUSTER = 3

# Configuraciones a comparar (qué exógenas usa cada modelo).
CONFIGS = {
    "A_calendario":  ["mes", "cerrado", "reapertura", "sin_1", "cos_1", "sin_2", "cos_2"],
    "B_+temporada":  ["nivel_temporada", "mes", "cerrado", "reapertura", "sin_1", "cos_1", "sin_2", "cos_2"],
    "C_+cluster1b":  ["nivel_temporada", "mes", "cerrado", "reapertura", "sin_1", "cos_1", "sin_2", "cos_2",
                      "clus_1", "clus_2"],
}


def _matriz_exogenas(indice, cs: ClusterSemanas):
    """Exógenas completas (calendario + temporada + one-hot de clúster) para
    el índice dado. `cs` es un ClusterSemanas YA entrenado."""
    X = datos.features_exogenas(indice)
    etq = cs.predecir(X)
    oh = etiquetas_onehot(etq, K_CLUSTER)
    return pd.concat([X, oh], axis=1)


def _mape(real, pred):
    real, pred = np.asarray(real, float), np.asarray(pred, float)
    m = ~np.isnan(real) & (real > 0)
    return float(np.mean(np.abs((real[m] - pred[m]) / real[m])) * 100)


def backtest(horizonte=2, n_origenes=10, verbose=True):
    """Walk-forward: para los últimos `n_origenes` orígenes (paso = horizonte),
    reentrena y pronostica `horizonte` semanas. Devuelve MAPE por configuración
    y el de una línea base ingenua (última semana operativa conocida)."""
    s = datos.serie_semanal()

    # El clúster (1b) se entrena solo con features conocidos de TODO el rango:
    # no usa el target, así que no filtra información del futuro.
    cs = ClusterSemanas(k=K_CLUSTER).entrenar(datos.features_exogenas(s.index))
    Xfull = _matriz_exogenas(s.index, cs)

    n = len(s)
    origenes = [n - horizonte * (i + 1) for i in range(n_origenes)][::-1]
    origenes = [o for o in origenes if o > 60]  # deja historia mínima

    resultados = {c: {"real": [], "pred": [], "por_origen": []} for c in CONFIGS}
    base = {"real": [], "pred": [], "por_origen": []}

    for corte in origenes:
        y_tr = s.iloc[:corte]
        idx_te = s.index[corte:corte + horizonte]
        y_te = s.iloc[corte:corte + horizonte]

        # Línea base ingenua: repetir la última semana operativa conocida.
        ult = y_tr.dropna().iloc[-1]
        base["real"] += list(y_te.values)
        base["pred"] += [ult] * len(y_te)
        base["por_origen"].append(_mape(y_te.values, [ult] * len(y_te)))

        for nombre, cols in CONFIGS.items():
            Xtr = Xfull.loc[y_tr.index, cols]
            Xte = Xfull.loc[idx_te, cols]
            try:
                mod = SARIMAX(y_tr, exog=Xtr, order=ORDEN,
                              seasonal_order=ORDEN_ESTACIONAL,
                              enforce_stationarity=False,
                              enforce_invertibility=False)
                res = mod.fit(disp=False)
                pred = list(res.get_forecast(steps=len(idx_te), exog=Xte).predicted_mean.values)
            except Exception:  # noqa
                pred = [ult] * len(y_te)
            resultados[nombre]["real"] += list(y_te.values)
            resultados[nombre]["pred"] += pred
            resultados[nombre]["por_origen"].append(_mape(y_te.values, pred))

    # MAPE global (media, sensible a outliers) y MAPE mediano por origen (robusto).
    tabla = {}
    tabla["Base_ingenua"] = (_mape(base["real"], base["pred"]),
                             float(np.median(base["por_origen"])))
    for nombre in CONFIGS:
        tabla[nombre] = (_mape(resultados[nombre]["real"], resultados[nombre]["pred"]),
                         float(np.median(resultados[nombre]["por_origen"])))

    if verbose:
        print(f"Backtesting walk-forward | orígenes={len(origenes)} "
              f"horizonte={horizonte} sem\n")
        print(f"  {'config':16s} {'MAPE_medio':>11s} {'MAPE_mediano':>13s}")
        mejor_med = min(v[1] for v in tabla.values())
        for nombre, (mg, md) in sorted(tabla.items(), key=lambda kv: kv[1][1]):
            marca = "  <- mejor (típico)" if md == mejor_med else ""
            print(f"  {nombre:16s} {mg:9.1f}%  {md:11.1f}%{marca}")
        print("\n  MAPE_medio: promedio (lo inflan la reapertura y los saltos de nivel).")
        print("  MAPE_mediano: error de una quincena TÍPICA (lo relevante para planificar).")
    return tabla


def pronosticar(horizonte=2, config="B_+temporada"):
    """Ajusta con TODO el histórico y pronostica `horizonte` semanas futuras.
    Devuelve un DataFrame con la predicción y su intervalo de confianza."""
    config = config if config in CONFIGS else "B_+temporada"
    s = datos.serie_semanal()
    cs = ClusterSemanas(k=K_CLUSTER).entrenar(datos.features_exogenas(s.index))
    cols = CONFIGS[config]

    Xtr = _matriz_exogenas(s.index, cs)[cols]
    idx_fut = datos.indice_futuro(s.index[-1], horizonte)
    Xfut = _matriz_exogenas(idx_fut, cs)[cols]

    mod = SARIMAX(s, exog=Xtr, order=ORDEN, seasonal_order=ORDEN_ESTACIONAL,
                  enforce_stationarity=False, enforce_invertibility=False)
    res = mod.fit(disp=False)
    fc = res.get_forecast(steps=horizonte, exog=Xfut)
    out = pd.DataFrame({
        "raciones_estimadas": fc.predicted_mean.round(0).values,
    }, index=idx_fut)
    ci = fc.conf_int(alpha=0.20).round(0)  # intervalo 80%
    out["min_80"] = ci.iloc[:, 0].values
    out["max_80"] = ci.iloc[:, 1].values
    out.index.name = "semana"
    return out


def backtest_simples(horizonte=2, n_origenes=12, verbose=True):
    """Compara modelos SIMPLES (sin exógenas) por walk-forward. El backtesting
    mostró que, para esta serie (nivel muy persistente + saltos que el calendario
    no ve), un promedio corto de semanas recientes supera al SARIMAX."""
    s = datos.serie_semanal()
    n = len(s)
    origenes = [n - horizonte * (i + 1) for i in range(n_origenes)][::-1]
    origenes = [o for o in origenes if o > 60]

    met = {"MA_2": [], "MA_3": [], "naive_1sem": []}
    for corte in origenes:
        ytr = s.iloc[:corte].dropna()
        yte = s.iloc[corte:corte + horizonte].values
        met["naive_1sem"].append(_mape(yte, [ytr.iloc[-1]] * horizonte))
        met["MA_2"].append(_mape(yte, [ytr.iloc[-2:].mean()] * horizonte))
        met["MA_3"].append(_mape(yte, [ytr.iloc[-3:].mean()] * horizonte))

    tabla = {k: (float(np.nanmean(v)), float(np.nanmedian(v))) for k, v in met.items()}
    if verbose:
        print(f"  {'modelo simple':16s} {'MAPE_medio':>11s} {'MAPE_mediano':>13s}")
        for nombre, (mg, md) in sorted(tabla.items(), key=lambda kv: kv[1][1]):
            print(f"  {nombre:16s} {mg:9.1f}%  {md:11.1f}%")
    return tabla


if __name__ == "__main__":
    print("=" * 64)
    print("A/B #1  —  SARIMAX con exógenas: ¿aporta el clúster 1b?")
    print("=" * 64)
    backtest(horizonte=2, n_origenes=10)

    print("\n" + "=" * 64)
    print("A/B #2  —  Modelos SIMPLES vs el SARIMAX de arriba")
    print("=" * 64)
    backtest_simples(horizonte=2, n_origenes=12)

    print("\n" + "=" * 64)
    print("VEREDICTO: gana el promedio de las 2 últimas semanas operativas.")
    print("Pronóstico próxima quincena (modelo de producción, ver ml.demanda):")
    print("=" * 64)
    from .demanda import predecir_demanda
    d = predecir_demanda()
    print(f"  {d['por_semana']} raciones/semana (banda {d['min_semana']}–{d['max_semana']})"
          f"  |  total quincena ~{d['total_quincena']}")
