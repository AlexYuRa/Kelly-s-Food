# -*- coding: utf-8 -*-
"""
Kelly's Food - Constructor de la base de datos SQLite
=====================================================
Toma los 39 archivos `datos_sql/kellys_food_transformado_YYYYMM.sql` que
entrega la Fase de Transformación (originalmente pensados para MySQL) y los
carga en un ÚNICO archivo SQLite `kellys_food.db`, adaptando la sintaxis.

La idea es que el programa de escritorio se entregue con la BD YA CARGADA:
este script se ejecuta una sola vez y produce el `.db`.

Adaptaciones MySQL -> SQLite:
    * `INT AUTO_INCREMENT PRIMARY KEY`  ->  `INTEGER PRIMARY KEY AUTOINCREMENT`
    * `INSERT IGNORE`                   ->  `INSERT OR IGNORE`
    * Se eliminan `CREATE DATABASE ...` y `USE ...` (SQLite no los usa).
    * VARCHAR / DECIMAL / DATE se conservan (SQLite los acepta).

Uso:
    py construir_bd.py
"""

import glob
import os
import re
import sqlite3
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
CARPETA_SQL = os.path.join(AQUI, "datos_sql")
RUTA_DB = os.path.join(AQUI, "kellys_food.db")

# Tablas que efectivamente contienen datos en el dataset.
TABLAS_PRINCIPALES = [
    "Trabajador", "Metodo_Pago", "Periodo_Cobro",
    "Racion", "Pago", "Menu", "Compra",
]


def adaptar_sql(texto: str) -> str:
    """Convierte un script pensado para MySQL a uno válido para SQLite."""
    # AUTO_INCREMENT: SQLite exige exactamente INTEGER PRIMARY KEY AUTOINCREMENT.
    texto = re.sub(
        r"\bINT\s+AUTO_INCREMENT\s+PRIMARY\s+KEY\b",
        "INTEGER PRIMARY KEY AUTOINCREMENT",
        texto,
        flags=re.IGNORECASE,
    )
    # Por si quedara algún AUTO_INCREMENT suelto.
    texto = re.sub(r"\bAUTO_INCREMENT\b", "", texto, flags=re.IGNORECASE)
    # INSERT IGNORE -> INSERT OR IGNORE
    texto = re.sub(r"\bINSERT\s+IGNORE\b", "INSERT OR IGNORE", texto, flags=re.IGNORECASE)

    # Quitar sentencias propias del servidor MySQL (línea a línea).
    lineas = []
    for linea in texto.splitlines():
        limpia = linea.strip()
        if re.match(r"(?i)^CREATE\s+DATABASE", limpia):
            continue
        if re.match(r"(?i)^USE\s+", limpia):
            continue
        lineas.append(linea)
    return "\n".join(lineas)


def archivos_sql() -> list:
    rutas = sorted(glob.glob(os.path.join(CARPETA_SQL, "kellys_food_transformado_*.sql")))
    if not rutas:
        raise SystemExit(f"No se encontraron .sql en {CARPETA_SQL}")
    return rutas


def construir(ruta_db: str = RUTA_DB) -> None:
    # La BD activa usa el modelo físico NORMALIZADO (ver kellys_food_norm.db).
    # Si existe esa copia maestra, se restaura desde ahí: los .sql de datos_sql/
    # corresponden al esquema antiguo denormalizado y ya no aplican.
    maestra = os.path.join(AQUI, "kellys_food_norm.db")
    if os.path.exists(maestra):
        import shutil
        shutil.copyfile(maestra, ruta_db)
        print(f"BD restaurada desde la copia maestra normalizada: {maestra}")
        return

    if os.path.exists(ruta_db):
        os.remove(ruta_db)
        print(f"BD anterior eliminada: {ruta_db}")

    conn = sqlite3.connect(ruta_db)
    conn.execute("PRAGMA foreign_keys = ON;")
    # PRAGMAs de carga rápida: sin estos, cada INSERT se sincroniza a disco por
    # separado y cargar ~96k filas tarda varios minutos. Solo afectan a la
    # construcción; la BD final funciona con los valores por defecto.
    conn.execute("PRAGMA synchronous = OFF;")
    conn.execute("PRAGMA journal_mode = MEMORY;")

    rutas = archivos_sql()
    print(f"Cargando {len(rutas)} archivos SQL en {ruta_db} ...\n")

    for i, ruta in enumerate(rutas, 1):
        with open(ruta, "r", encoding="utf-8") as f:
            sql = adaptar_sql(f.read())
        try:
            conn.executescript(sql)
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            print(f"  [ERROR] {os.path.basename(ruta)}: {e}")
            raise
        print(f"  [{i:2}/{len(rutas)}] {os.path.basename(ruta)}  OK")

    print("\nResumen de filas por tabla:")
    cur = conn.cursor()
    for tabla in TABLAS_PRINCIPALES:
        try:
            n = cur.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
            print(f"  {tabla:<15} {n:>8}")
        except sqlite3.Error as e:
            print(f"  {tabla:<15} (sin datos) {e}")

    # Índices que aceleran las consultas del programa.
    print("\nCreando índices de apoyo ...")
    indices = [
        "CREATE INDEX IF NOT EXISTS idx_racion_trab ON Racion(id_trabajador);",
        "CREATE INDEX IF NOT EXISTS idx_racion_fecha ON Racion(Fecha);",
        "CREATE INDEX IF NOT EXISTS idx_pago_trab ON Pago(id_trabajador);",
        "CREATE INDEX IF NOT EXISTS idx_pago_fecha ON Pago(Fecha_pago);",
        "CREATE INDEX IF NOT EXISTS idx_compra_fecha ON Compra(Fecha);",
    ]
    for idx in indices:
        conn.execute(idx)
    conn.commit()
    conn.close()
    print(f"\nBase de datos creada correctamente: {ruta_db}")


if __name__ == "__main__":
    construir()
    sys.exit(0)
