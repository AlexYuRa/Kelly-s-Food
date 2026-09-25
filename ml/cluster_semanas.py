# -*- coding: utf-8 -*-
"""
1b · K-Means de semanas (versión CORREGIDA, anti-fuga de datos)
===============================================================
La propuesta original —agrupar semanas por su NIVEL DE CONSUMO y usar esa
etiqueta como exógena— es circular: para conocer el clúster de una semana futura
habría que conocer su consumo, que es justo lo que queremos predecir.

Aquí el K-Means se entrena SOLO con features conocidos de antemano (temporada,
calendario). Así el clúster de cualquier semana futura es calculable sin mirar el
target. La etiqueta resultante (0/1/2) se puede pasar a SARIMAX como una exógena
interpretable ("semana tipo pico/promedio/baja") y medir si aporta.
"""

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from . import datos

# Features CONOCIDOS sobre los que se agrupa (nunca el consumo).
_COLS_CLUSTER = ["nivel_temporada", "sin_1", "cos_1", "sin_2", "cos_2"]


class ClusterSemanas:
    """Asigna a cada semana un clúster a partir de features conocidos."""

    def __init__(self, k: int = 3, semilla: int = 2026):
        self.k = k
        self.semilla = semilla
        self.scaler = StandardScaler()
        self.km = KMeans(n_clusters=k, random_state=semilla, n_init=10)
        self._orden = None  # remapea etiquetas a orden estable

    def entrenar(self, X: pd.DataFrame) -> "ClusterSemanas":
        Z = self.scaler.fit_transform(X[_COLS_CLUSTER])
        etiquetas = self.km.fit_predict(Z)
        # Reordena las etiquetas por nivel_temporada medio para que sean estables
        # e interpretables (0=más baja, k-1=más alta) entre corridas.
        medias = pd.Series(X["nivel_temporada"].values).groupby(etiquetas).mean()
        self._orden = {viejo: nuevo for nuevo, viejo in
                       enumerate(medias.sort_values().index)}
        return self

    def predecir(self, X: pd.DataFrame) -> pd.Series:
        Z = self.scaler.transform(X[_COLS_CLUSTER])
        crudo = self.km.predict(Z)
        mapeado = np.array([self._orden[c] for c in crudo])
        return pd.Series(mapeado, index=X.index, name="cluster_semana")


def etiquetas_onehot(cluster: pd.Series, k: int) -> pd.DataFrame:
    """One-hot de la etiqueta de clúster (deja fuera la 0 para evitar
    colinealidad con la constante del modelo)."""
    dummies = pd.get_dummies(cluster, prefix="clus").astype(float)
    for c in range(k):
        col = f"clus_{c}"
        if col not in dummies:
            dummies[col] = 0.0
    dummies = dummies[[f"clus_{c}" for c in range(k)]]
    return dummies.iloc[:, 1:]  # descarta clus_0 (categoría base)


if __name__ == "__main__":
    s = datos.serie_semanal()
    X = datos.features_exogenas(s.index)
    cs = ClusterSemanas(k=3).entrenar(X)
    etq = cs.predecir(X)
    resumen = (pd.concat([s.rename("raciones"), etq], axis=1)
                 .dropna()
                 .groupby("cluster_semana")["raciones"]
                 .agg(["count", "mean", "min", "max"]))
    print("Perfil de los clústeres de semana (validación, mira el consumo real):")
    print(resumen.round(0))
    print("\nNota: el clúster se armó SOLO con temporada+calendario; que el "
          "consumo medio se separe por grupo confirma que la señal es útil.")
