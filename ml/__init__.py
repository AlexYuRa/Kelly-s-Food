# -*- coding: utf-8 -*-
"""
Kelly's Food - Modelos de ciencia de datos
==========================================
Paquete de análisis y predicción. NO altera la base operativa: todo lo que lee
es de solo lectura sobre kellys_food.db (modelo normalizado). Si en el futuro se
guardan resultados, irán a tablas con prefijo `ml_` separadas del diagrama.

Módulos:
  * datos            -> extracción de la serie semanal + features exógenas.
  * cluster_semanas  -> 1b: K-Means de semanas sobre features CONOCIDOS (anti-leakage).
  * pronostico       -> #1: SARIMAX con exógenas + backtesting walk-forward.
"""
