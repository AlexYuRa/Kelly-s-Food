# -*- coding: utf-8 -*-
"""
Modelo de producción de demanda + sugerencia de compra (LIGERO)
===============================================================
Este módulo es el que consume la APP. A propósito NO importa statsmodels ni
scikit-learn (solo pandas): el backtesting eligió un modelo simple —promedio de
las 2 últimas semanas operativas— que le gana al SARIMAX, así que la app arranca
rápida. La evidencia que justifica esa elección vive en `ml.pronostico`.

Todo es de SOLO LECTURA. No crea ni modifica tablas: la sugerencia se calcula al
vuelo cada vez que se muestra.
"""

import pandas as pd

from . import datos

# Nº de semanas operativas recientes que promedia el modelo (elegido por MAPE).
VENTANA_PRODUCCION = 2
# Semanas de una quincena (para el total del período).
SEMANAS_QUINCENA = 2


def predecir_demanda(ventana: int = VENTANA_PRODUCCION) -> dict:
    """Estima las raciones POR SEMANA de la próxima quincena: promedio de las
    `ventana` últimas semanas operativas, con una banda de ±1 desviación de las
    últimas 8 semanas como margen de compra. Devuelve un dict listo para la UI."""
    s = datos.serie_semanal()
    oper = s.dropna()
    if len(oper) < ventana:
        return {}
    nivel = float(oper.iloc[-ventana:].mean())
    margen = float(oper.iloc[-8:].std()) if len(oper) >= 3 else 0.0
    idx_fut = datos.indice_futuro(s.index[-1], SEMANAS_QUINCENA)
    return {
        "por_semana": round(nivel),
        "min_semana": max(0, round(nivel - margen)),
        "max_semana": round(nivel + margen),
        "total_quincena": round(nivel * SEMANAS_QUINCENA),
        "min_quincena": max(0, round((nivel - margen) * SEMANAS_QUINCENA)),
        "max_quincena": round((nivel + margen) * SEMANAS_QUINCENA),
        "semana_desde": idx_fut[0].date().isoformat(),
        "semana_hasta": idx_fut[-1].date().isoformat(),
        "ventana": ventana,
    }


def _consumo_por_racion(dias: int = 90) -> pd.DataFrame:
    """Consumo típico de cada insumo POR RACIÓN, ponderado por las raciones
    realmente servidas en los últimos `dias` con receta. Incluye la merma.

    cantidad_por_racion(i) = SUM_d[ raciones(d) * Cant_Usada(i,d) * (1+merma) ]
                             / SUM_d[ raciones(d) ]
    """
    con = datos._conectar()
    try:
        # Raciones por fecha (para ponderar).
        rac = pd.read_sql(
            "SELECT Fecha_Menu, COUNT(*) AS raciones FROM racion_relacional "
            "GROUP BY Fecha_Menu", con, parse_dates=["Fecha_Menu"])
        # Receta por fecha e insumo (cantidad por ración + merma).
        rec = pd.read_sql(
            """SELECT rr.Fecha_Menu, rr.ID_Insumo, i.Nombre_Insumo,
                      um.Descripcion AS unidad,
                      r.Cantidad_Usada, r.Porcentaje_Merma
               FROM receta_relacional rr
               JOIN receta r  ON rr.ID_Receta = r.ID_Receta
               JOIN insumo i  ON rr.ID_Insumo = i.ID_Insumo
               LEFT JOIN unidad_medida um ON i.ID_Unidad_M = um.ID_Unidad_M""",
            con, parse_dates=["Fecha_Menu"])
        # Costo unitario reciente por insumo (para estimar soles).
        costo = pd.read_sql(
            "SELECT ID_Insumo, Costo_Adquisicion, Cantidad FROM detallecompra", con)
    finally:
        con.close()

    if rec.empty or rac.empty:
        return pd.DataFrame()

    corte = rac["Fecha_Menu"].max() - pd.Timedelta(days=dias)
    rac = rac[rac["Fecha_Menu"] >= corte]
    rec = rec[rec["Fecha_Menu"] >= corte]

    m = rec.merge(rac, on="Fecha_Menu", how="inner")
    m["cant_dia"] = (m["raciones"] * m["Cantidad_Usada"]
                     * (1 + m["Porcentaje_Merma"] / 100.0))
    total_rac = rac["raciones"].sum()

    g = (m.groupby(["ID_Insumo", "Nombre_Insumo", "unidad"], as_index=False)
           .agg(cant_total=("cant_dia", "sum")))
    g["por_racion"] = g["cant_total"] / total_rac

    # Costo unitario (soles por unidad de insumo) = costo/ cantidad, promedio.
    if not costo.empty:
        costo = costo[costo["Cantidad"] > 0].copy()
        costo["unit"] = costo["Costo_Adquisicion"] / costo["Cantidad"]
        cu = costo.groupby("ID_Insumo", as_index=False)["unit"].mean()
        g = g.merge(cu, on="ID_Insumo", how="left")
    else:
        g["unit"] = 0.0
    g["unit"] = g["unit"].fillna(0.0)
    return g[["Nombre_Insumo", "unidad", "por_racion", "unit"]]


def sugerir_compra(total_raciones: int, dias: int = 90, top: int = None) -> pd.DataFrame:
    """Traduce un total de raciones a cantidades de insumo a comprar (con merma)
    y su costo estimado. Ordenado por costo estimado desc."""
    base = _consumo_por_racion(dias)
    if base.empty:
        return base
    base = base.copy()
    base["cantidad"] = (base["por_racion"] * total_raciones).round(1)
    base["costo_estimado"] = (base["cantidad"] * base["unit"]).round(2)
    base = base.rename(columns={"Nombre_Insumo": "insumo"})
    # Se ordena por CANTIDAD: el costo solo existe para 6/30 insumos en
    # detallecompra, así que no sirve como criterio principal.
    base = base.sort_values("cantidad", ascending=False)
    cols = ["insumo", "unidad", "cantidad", "costo_estimado"]
    out = base[cols].reset_index(drop=True)
    return out.head(top) if top else out


if __name__ == "__main__":
    d = predecir_demanda()
    print("Pronóstico próxima quincena:")
    print(f"  {d['por_semana']} raciones/semana (banda {d['min_semana']}–{d['max_semana']})")
    print(f"  Total quincena ({d['semana_desde']} .. {d['semana_hasta']}): "
          f"~{d['total_quincena']} raciones\n")
    print(f"Sugerencia de compra para ~{d['total_quincena']} raciones:")
    print(sugerir_compra(d["total_quincena"]).to_string(index=False))
