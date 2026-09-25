# -*- coding: utf-8 -*-
"""
Extracción de datos y construcción de features exógenas para el pronóstico (#1).
================================================================================
Todo es de SOLO LECTURA sobre kellys_food.db.

Serie objetivo (endógena)
-------------------------
Raciones agregadas por semana (W-SUN). Se trabaja a nivel semanal porque:
  * es la unidad natural de planificación de compras (más estable que la diaria),
  * se agrega fácil a la quincena (unidad de cobranza),
  * da ~157 semanas operativas de historia (suficiente para SARIMAX).

Las semanas de CIERRE (fin de año, sin operación) se marcan como NaN en vez de 0:
SARIMAX las trata como observaciones faltantes vía el filtro de Kalman, sin que
el modelo aprenda un "bajón" que en realidad es un feriado. La última semana, si
está incompleta (corte de datos), se descarta.

Features exógenas (TODAS conocidas de antemano -> válidas para pronosticar)
--------------------------------------------------------------------------
  * nivel_temporada : 3=Alta, 2=Media, 1=Baja  (tabla temporada/clasi_temporada)
  * mes             : 1..12
  * fourier_*       : armónicos anuales (sin/cos) para la estacionalidad de año
  * cerrado         : 1 si la semana cae en un cierre conocido (Dic-Ene)

NO se usan features derivados del consumo (eso sería fuga de datos).
"""

import os
import sqlite3

import numpy as np
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
RUTA_DB = os.path.join(os.path.dirname(AQUI), "kellys_food.db")

# Periodo anual en semanas (365.25 / 7).
PERIODO_ANUAL = 365.25 / 7.0
# Umbral: una semana con menos raciones que esto se considera cierre/incompleta.
UMBRAL_CIERRE = 60


def _conectar() -> sqlite3.Connection:
    if not os.path.exists(RUTA_DB):
        raise FileNotFoundError(f"No existe la base de datos '{RUTA_DB}'.")
    return sqlite3.connect(RUTA_DB)


def serie_semanal(recortar_parcial: bool = True) -> pd.Series:
    """Raciones por semana (índice W-SUN). Cierres -> NaN; semana parcial final
    descartada. Devuelve una Serie float con índice datetime regular."""
    con = _conectar()
    try:
        df = pd.read_sql(
            "SELECT Fecha_Menu FROM racion_relacional",
            con, parse_dates=["Fecha_Menu"])
    finally:
        con.close()

    s = (df.set_index("Fecha_Menu")
           .assign(n=1)
           .resample("W-SUN")["n"].sum()
           .astype(float))

    # La última semana suele estar incompleta (corte de datos): si es
    # claramente parcial respecto a la anterior, se descarta.
    if recortar_parcial and len(s) >= 2 and s.iloc[-1] < UMBRAL_CIERRE:
        s = s.iloc[:-1]

    # Cierres (semanas casi vacías dentro del rango) -> NaN (faltante real).
    s = s.mask(s < UMBRAL_CIERRE, np.nan)
    s.name = "raciones"
    return s


def _nivel_temporada_por_fecha(fechas: pd.DatetimeIndex) -> pd.Series:
    """Mapea cada fecha al nivel de demanda de su temporada (3/2/1)."""
    con = _conectar()
    try:
        temp = pd.read_sql(
            """SELECT t.Fecha_Inicio, t.Fecha_Fin, cl.Nombre_Clasi
               FROM temporada t JOIN clasi_temporada cl ON t.ID_Clasi = cl.ID_Clasi""",
            con, parse_dates=["Fecha_Inicio", "Fecha_Fin"])
    finally:
        con.close()

    nivel = {"Alta demanda": 3, "Media demanda": 2, "Baja demanda": 1}
    out = pd.Series(2.0, index=fechas)  # por defecto: media
    for _, r in temp.iterrows():
        mask = (fechas >= r["Fecha_Inicio"]) & (fechas <= r["Fecha_Fin"])
        out[mask] = nivel.get(r["Nombre_Clasi"], 2)
    return out


def features_exogenas(indice: pd.DatetimeIndex, n_fourier: int = 2) -> pd.DataFrame:
    """Construye el DataFrame de exógenas para el índice dado (histórico o
    futuro). Todas las columnas son conocibles de antemano."""
    idx = pd.DatetimeIndex(indice)
    X = pd.DataFrame(index=idx)
    X["nivel_temporada"] = _nivel_temporada_por_fecha(idx).values
    X["mes"] = idx.month
    X["cerrado"] = ((idx.month == 1) | ((idx.month == 12) & (idx.day >= 1))).astype(int)
    # Reapertura tras el cierre de fin de año: las primeras semanas de febrero la
    # operación arranca "en rampa" (volumen bajo). Es conocible de antemano y
    # evita que el modelo sobreestime al salir de las semanas cerradas (NaN).
    X["reapertura"] = ((idx.month == 2) & (idx.day <= 15)).astype(int)

    # Armónicos anuales (estacionalidad de año sin recurrir a s=52).
    semana_del_anio = idx.isocalendar().week.astype(float).values
    for k in range(1, n_fourier + 1):
        ang = 2.0 * np.pi * k * semana_del_anio / PERIODO_ANUAL
        X[f"sin_{k}"] = np.sin(ang)
        X[f"cos_{k}"] = np.cos(ang)
    return X


def indice_futuro(ultima_fecha: pd.Timestamp, pasos: int) -> pd.DatetimeIndex:
    """Genera el índice semanal (W-SUN) de las próximas `pasos` semanas."""
    return pd.date_range(start=ultima_fecha + pd.Timedelta(weeks=1),
                         periods=pasos, freq="W-SUN")


if __name__ == "__main__":
    s = serie_semanal()
    print(f"Serie semanal: {len(s)} semanas | faltantes(NaN)={int(s.isna().sum())}")
    print(f"Rango: {s.index.min().date()} .. {s.index.max().date()}")
    print(f"Raciones/semana operativa: min={s.min():.0f} med={s.median():.0f} max={s.max():.0f}")
    X = features_exogenas(s.index)
    print("\nExógenas (cabecera):")
    print(X.head())
    print("\nCorrelación nivel_temporada vs raciones:",
          round(pd.concat([s, X["nivel_temporada"]], axis=1).corr().iloc[0, 1], 3))
