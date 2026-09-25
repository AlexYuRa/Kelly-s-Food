# -*- coding: utf-8 -*-
"""
Kelly's Food - Exportador de backup en formato MySQL
====================================================
La aplicación trabaja sobre SQLite (`kellys_food.db`), pero el informe declara
la base en MySQL. Este script NO migra la aplicación: solo LEE la BD SQLite y
genera un archivo `.sql` estilo `mysqldump` (esquema + datos) que se importa en
cualquier servidor MySQL/MariaDB. Así el profesor obtiene un backup en MySQL sin
cambiar nada del programa.

El dump:
  * Reconstruye cada tabla con tipos MySQL (INT, VARCHAR, DECIMAL, DATE, ...).
  * Conserva llaves primarias y foráneas del modelo normalizado.
  * Usa ENGINE=InnoDB y CHARSET=utf8mb4.
  * Desactiva FOREIGN_KEY_CHECKS durante la carga para no depender del orden.

Uso:
    py exportar_mysql.py                      # genera backup_kellys_food_mysql.sql
    py exportar_mysql.py otra_salida.sql      # nombre de salida a elección
"""

import os
import sqlite3
import sys
from datetime import datetime

AQUI = os.path.dirname(os.path.abspath(__file__))
RUTA_DB = os.path.join(AQUI, "kellys_food.db")
SALIDA_DEF = os.path.join(AQUI, "backup_kellys_food_mysql.sql")

# Orden de creación por dependencias (padres antes que hijos). Las no listadas
# se agregan al final en orden alfabético.
ORDEN = [
    "clasi_temporada", "distrito", "urbanizacion", "estado_trabajador",
    "metodo_pago", "periodo_cobro", "tipo_insumo", "unidad_medida",
    "Precio_Menu", "temporada", "proveedor", "insumo", "trabajador",
    "menu", "compra", "pago", "racion", "receta",
    "tel_proveedor", "tel_trabajador", "precio_trabajador",
    "compra_relacional", "detallecompra", "racion_relacional",
    "receta_relacional",
]

FILAS_POR_INSERT = 500


def tablas(conn) -> list:
    todas = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%'")]
    ordenadas = [t for t in ORDEN if t in todas]
    ordenadas += sorted(t for t in todas if t not in ORDEN)
    return ordenadas


def tipo_mysql(decl: str, col: str) -> str:
    """Traduce el tipo declarado de SQLite al equivalente en MySQL."""
    d = (decl or "").upper()
    if "CHAR" in d:            # VARCHAR(n) / CHAR(n): se conservan tal cual
        return decl
    if "INT" in d:
        return "INT"
    if "DECIMAL" in d or "NUMERIC" in d:
        return decl
    if "REAL" in d or "DOUB" in d or "FLOA" in d:
        return "DOUBLE"
    if "DATE" in d or "TIME" in d:
        return "DATE"
    if "TEXT" in d:
        # Fecha_Desde se guarda como texto ISO -> DATE; el resto texto corto.
        return "DATE" if "FECHA" in col.upper() else "VARCHAR(255)"
    return "VARCHAR(255)"


def ddl_tabla(conn, tabla: str) -> str:
    cols = conn.execute(f'PRAGMA table_info("{tabla}")').fetchall()
    # cid, name, type, notnull, dflt_value, pk
    fks = conn.execute(f'PRAGMA foreign_key_list("{tabla}")').fetchall()
    pk_cols = [c for c in cols if c[5] > 0]
    pk_cols.sort(key=lambda c: c[5])
    pk_simple = len(pk_cols) == 1

    lineas = []
    for cid, nombre, tipo, notnull, dflt, pk in cols:
        t = tipo_mysql(tipo, nombre)
        pieza = f"  `{nombre}` {t}"
        es_pk = pk > 0
        if notnull or es_pk:
            pieza += " NOT NULL"
        if dflt is not None:
            pieza += f" DEFAULT {dflt}"
        # AUTO_INCREMENT solo para PK entera simple con nombre ID_*.
        if (pk_simple and es_pk and t == "INT"
                and nombre.upper().startswith("ID_")):
            pieza += " AUTO_INCREMENT"
        lineas.append(pieza)

    if pk_cols:
        campos = ", ".join(f"`{c[1]}`" for c in pk_cols)
        lineas.append(f"  PRIMARY KEY ({campos})")

    for _id, _seq, tabla_ref, desde, hacia, *_ in fks:
        lineas.append(f"  FOREIGN KEY (`{desde}`) REFERENCES "
                      f"`{tabla_ref}` (`{hacia}`)")

    cuerpo = ",\n".join(lineas)
    return (f"DROP TABLE IF EXISTS `{tabla}`;\n"
            f"CREATE TABLE `{tabla}` (\n{cuerpo}\n"
            f") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;\n")


def valor(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, (int,)):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, bytes):
        v = v.decode("utf-8", "replace")
    s = str(v).replace("\\", "\\\\").replace("'", "\\'")
    s = s.replace("\r", "\\r").replace("\n", "\\n")
    return f"'{s}'"


def datos_tabla(conn, tabla: str) -> str:
    cur = conn.execute(f'SELECT * FROM "{tabla}"')
    columnas = [d[0] for d in cur.description]
    cols_sql = ", ".join(f"`{c}`" for c in columnas)
    partes, lote = [], []
    filas = cur.fetchall()
    if not filas:
        return ""
    for fila in filas:
        lote.append("(" + ", ".join(valor(v) for v in fila) + ")")
        if len(lote) >= FILAS_POR_INSERT:
            partes.append(f"INSERT INTO `{tabla}` ({cols_sql}) VALUES\n"
                          + ",\n".join(lote) + ";")
            lote = []
    if lote:
        partes.append(f"INSERT INTO `{tabla}` ({cols_sql}) VALUES\n"
                      + ",\n".join(lote) + ";")
    return "\n".join(partes) + "\n"


def exportar(ruta_db: str = RUTA_DB, salida: str = SALIDA_DEF) -> None:
    if not os.path.exists(ruta_db):
        raise SystemExit(f"No existe la BD: {ruta_db}")
    conn = sqlite3.connect(ruta_db)
    conn.text_factory = str
    lista = tablas(conn)

    with open(salida, "w", encoding="utf-8") as f:
        f.write("-- ===================================================\n")
        f.write("-- Kelly's Food - Backup en formato MySQL\n")
        f.write(f"-- Generado: {datetime.now():%Y-%m-%d %H:%M:%S}\n")
        f.write(f"-- Origen: {os.path.basename(ruta_db)} (SQLite, modelo normalizado)\n")
        f.write("-- Importar:  mysql -u root -p kellys_food < "
                f"{os.path.basename(salida)}\n")
        f.write("-- ===================================================\n\n")
        f.write("CREATE DATABASE IF NOT EXISTS `kellys_food` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;\n")
        f.write("USE `kellys_food`;\n\n")
        f.write("SET NAMES utf8mb4;\n")
        f.write("SET FOREIGN_KEY_CHECKS = 0;\n")
        f.write("SET SQL_MODE = 'NO_AUTO_VALUE_ON_ZERO';\n\n")

        for tabla in lista:
            n = conn.execute(f'SELECT COUNT(*) FROM "{tabla}"').fetchone()[0]
            f.write(f"-- ----- Tabla `{tabla}` ({n} filas) -----\n")
            f.write(ddl_tabla(conn, tabla))
            f.write("\n")
            datos = datos_tabla(conn, tabla)
            if datos:
                f.write(datos)
            f.write("\n")

        f.write("SET FOREIGN_KEY_CHECKS = 1;\n")

    conn.close()
    tam = os.path.getsize(salida) / (1024 * 1024)
    print(f"Backup MySQL generado: {salida}  ({tam:.1f} MB, {len(lista)} tablas)")


if __name__ == "__main__":
    destino = sys.argv[1] if len(sys.argv) > 1 else SALIDA_DEF
    exportar(salida=destino)
