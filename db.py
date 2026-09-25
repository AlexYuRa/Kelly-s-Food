# -*- coding: utf-8 -*-
"""
Kelly's Food - Capa de acceso a datos (SQLite, modelo normalizado)
==================================================================
Toda la interacción con la base de datos pasa por aquí. La BD sigue el modelo
físico normalizado (trabajador con DNI, ración por unidad, pago con ID_Metodo/
ID_Periodo, catálogos, abastecimiento). Esta capa presenta esos datos a la
interfaz con las MISMAS formas de retorno de siempre, así las vistas no cambian:
  * `id_trabajador` expuesto = ID_Trabajador (el código propio del trabajador,
    p. ej. 001ALCO; clave opaca para la UI).
  * `Nombre`  = Primer (+ Segundo) nombre.
  * `Apellido` = Apellido paterno + materno.
"""

import os
import sqlite3
from datetime import date, timedelta

AQUI = os.path.dirname(os.path.abspath(__file__))
RUTA_DB = os.path.join(AQUI, "kellys_food.db")

# Estados (catálogo estado_trabajador).
ESTADO_ACTIVO = "Activo"
ESTADO_TEMPORAL = "Baja temporal"
ESTADO_DEFINITIVA = "Baja definitiva"
_ESTADO_ID = {ESTADO_ACTIVO: 1, ESTADO_TEMPORAL: 2, ESTADO_DEFINITIVA: 3}

# Fragmentos SQL para componer nombre/apellido/teléfono desde el modelo.
_NOMBRE = ("(t.Primer_Nombre_Trabajador || CASE WHEN "
           "t.Segundo_Nombre_Trabajador IS NOT NULL AND "
           "t.Segundo_Nombre_Trabajador <> '' THEN ' ' || "
           "t.Segundo_Nombre_Trabajador ELSE '' END)")
_APELLIDO = "(t.Apellido_paterno || ' ' || t.Apellido_materno)"
_TEL = ("(SELECT Telefono_Trabajador FROM tel_trabajador te "
        "WHERE te.ID_Trabajador = t.ID_Trabajador LIMIT 1)")


# =====================================================================
# Conexión y helpers genéricos
# =====================================================================
def conectar() -> sqlite3.Connection:
    if not os.path.exists(RUTA_DB):
        raise FileNotFoundError(
            f"No existe la base de datos '{RUTA_DB}'. Ejecuta:  py construir_bd.py")
    conn = sqlite3.connect(RUTA_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def consultar(sql: str, params=()) -> list:
    conn = conectar()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def ejecutar(sql: str, params=()) -> int:
    conn = conectar()
    try:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid if sql.strip().upper().startswith("INSERT") else cur.rowcount
    finally:
        conn.close()


# =====================================================================
# Tablas editables por el CRUD genérico (Compra, Metodo_Pago, Periodo_Cobro)
# =====================================================================
TABLAS = {
    "Compra": {
        "titulo": "Compras",
        "pk": ["ID_Compra"],
        "auto": True,
        "columnas": [
            ("ID_Compra", "ID Compra", "entero", False),
            ("Concepto", "Concepto (insumo)", "texto", True),
            ("Fecha", "Fecha", "fecha", True),
            ("Monto", "Monto", "decimal", True),
        ],
        "fk": {},
    },
    "Metodo_Pago": {
        "titulo": "Métodos de pago",
        "sql": "metodo_pago",
        "pk": ["ID_Metodo"],
        "auto": True,
        "columnas": [
            ("ID_Metodo", "ID", "entero", False),
            ("Descripcion", "Método de pago", "texto", True),
        ],
        "fk": {},
    },
    "Periodo_Cobro": {
        "titulo": "Períodos de cobro",
        "sql": "periodo_cobro",
        "pk": ["ID_Periodo"],
        "auto": True,
        "columnas": [
            ("ID_Periodo", "ID", "entero", False),
            ("Codigo", "Código", "texto", True),
            ("Descripcion", "Descripción", "texto", True),
            ("Fecha_Inicio", "Desde", "fecha", True),
            ("Fecha_Fin", "Hasta", "fecha", True),
        ],
        "fk": {},
    },
}


# =====================================================================
# CRUD genérico
# =====================================================================
def _insumo_id(nombre: str) -> int:
    fila = consultar("SELECT ID_Insumo i FROM insumo WHERE Nombre_Insumo = ? "
                     "COLLATE NOCASE", (nombre.strip(),))
    if fila:
        return fila[0]["i"]
    return consultar("SELECT ID_Insumo i FROM insumo WHERE Nombre_Insumo = "
                     "'Insumos Perecibles'")[0]["i"]


def listar(tabla: str, busqueda: str = "", limite: int = 1000) -> list:
    if tabla == "Compra":
        sql = ("SELECT c.ID_Compra AS ID_Compra, i.Nombre_Insumo AS Concepto, "
               "c.Fecha_Transaccion AS Fecha, d.Costo_Adquisicion AS Monto "
               "FROM compra c "
               "JOIN detallecompra d ON d.ID_Compra = c.ID_Compra "
               "JOIN insumo i ON i.ID_Insumo = d.ID_Insumo")
        params = []
        if busqueda.strip():
            like = f"%{busqueda.strip()}%"
            sql += (" WHERE CAST(c.ID_Compra AS TEXT) LIKE ? OR i.Nombre_Insumo "
                    "LIKE ? OR c.Fecha_Transaccion LIKE ? OR "
                    "CAST(d.Costo_Adquisicion AS TEXT) LIKE ?")
            params = [like] * 4
        sql += " ORDER BY c.ID_Compra LIMIT ?"
        params.append(limite)
        return consultar(sql, params)

    meta = TABLAS[tabla]
    tabla_sql = meta.get("sql", tabla)
    cols = [c[0] for c in meta["columnas"]]
    sql = f"SELECT {', '.join(cols)} FROM {tabla_sql}"
    params = []
    if busqueda.strip():
        cond = [f"CAST({c} AS TEXT) LIKE ?" for c in cols]
        sql += " WHERE " + " OR ".join(cond)
        params = [f"%{busqueda.strip()}%"] * len(cols)
    sql += f" ORDER BY {meta['pk'][0]} LIMIT ?"
    params.append(limite)
    return consultar(sql, params)


def insertar(tabla: str, datos: dict) -> int:
    if tabla == "Compra":
        return _insertar_compra(datos)
    meta = TABLAS[tabla]
    tabla_sql = meta.get("sql", tabla)
    cols = list(datos.keys())
    marcadores = ", ".join(["?"] * len(cols))
    return ejecutar(f"INSERT INTO {tabla_sql} ({', '.join(cols)}) VALUES "
                    f"({marcadores})", list(datos.values()))


def actualizar(tabla: str, datos: dict, pk_valores: dict) -> int:
    if tabla == "Trabajador":
        return _actualizar_trabajador(datos, pk_valores["id_trabajador"])
    if tabla == "Compra":
        return _actualizar_compra(datos, pk_valores["ID_Compra"])
    meta = TABLAS[tabla]
    tabla_sql = meta.get("sql", tabla)
    set_ = ", ".join([f"{c} = ?" for c in datos])
    where = " AND ".join([f"{c} = ?" for c in pk_valores])
    return ejecutar(f"UPDATE {tabla_sql} SET {set_} WHERE {where}",
                    list(datos.values()) + list(pk_valores.values()))


def eliminar(tabla: str, pk_valores: dict) -> int:
    if tabla == "Compra":
        cid = pk_valores["ID_Compra"]
        conn = conectar()
        try:
            conn.execute("DELETE FROM compra_relacional WHERE ID_Compra = ?", (cid,))
            conn.execute("DELETE FROM detallecompra WHERE ID_Compra = ?", (cid,))
            n = conn.execute("DELETE FROM compra WHERE ID_Compra = ?", (cid,)).rowcount
            conn.commit()
            return n
        finally:
            conn.close()
    meta = TABLAS[tabla]
    tabla_sql = meta.get("sql", tabla)
    where = " AND ".join([f"{c} = ?" for c in pk_valores])
    return ejecutar(f"DELETE FROM {tabla_sql} WHERE {where}",
                    list(pk_valores.values()))


def _insertar_compra(datos: dict) -> int:
    ins = _insumo_id(datos["Concepto"])
    fecha = datos["Fecha"]
    monto = datos["Monto"]
    ruc = consultar("SELECT RUC FROM proveedor LIMIT 1")[0]["RUC"]
    temp = _temporada_de(fecha)
    conn = conectar()
    try:
        cid = conn.execute("INSERT INTO compra (Fecha_Transaccion) VALUES (?)",
                           (fecha,)).lastrowid
        conn.execute("INSERT INTO detallecompra (ID_Insumo, ID_Compra, Cantidad, "
                     "Costo_Adquisicion) VALUES (?,?,?,?)", (ins, cid, 1, monto))
        conn.execute("INSERT INTO compra_relacional (ID_Compra, RUC, ID_Temporada) "
                     "VALUES (?,?,?)", (cid, ruc, temp))
        conn.commit()
        return cid
    finally:
        conn.close()


def _actualizar_compra(datos: dict, cid) -> int:
    ins = _insumo_id(datos["Concepto"])
    conn = conectar()
    try:
        conn.execute("UPDATE compra SET Fecha_Transaccion = ? WHERE ID_Compra = ?",
                     (datos["Fecha"], cid))
        conn.execute("UPDATE detallecompra SET ID_Insumo = ?, Costo_Adquisicion = ? "
                     "WHERE ID_Compra = ?", (ins, datos["Monto"], cid))
        conn.commit()
        return 1
    finally:
        conn.close()


# ---------------------------------------------------------------
# Compras — API amigable para la clienta (por nombre, sin IDs).
# La compra son 3 tablas (compra + detallecompra + compra_relacional); aquí se
# manejan juntas y el id_compra se genera solo. Fiel al modelo: 1 insumo por
# compra (en los datos no hay compras con más de un detalle).
# ---------------------------------------------------------------
def insumos_conocidos() -> list:
    """[(nombre, unidad)] de los insumos, para el combo de compras."""
    return [(f["Nombre_Insumo"], f["unidad"]) for f in consultar(
        "SELECT i.Nombre_Insumo, COALESCE(um.Descripcion,'') AS unidad "
        "FROM insumo i LEFT JOIN unidad_medida um ON i.ID_Unidad_M = um.ID_Unidad_M "
        "ORDER BY i.Nombre_Insumo COLLATE NOCASE")]


def proveedores_conocidos() -> list:
    """[(ruc, nombre)] de proveedores; el nombre es el que ve la clienta."""
    return [(f["RUC"], f["Primer_Nombre_Proveedor"]) for f in consultar(
        "SELECT RUC, Primer_Nombre_Proveedor FROM proveedor "
        "ORDER BY Primer_Nombre_Proveedor COLLATE NOCASE")]


def compras_recientes(busqueda: str = "", limite: int = 500) -> list:
    """Compras ordenadas de la más reciente; por nombre de insumo y proveedor."""
    sql = ("SELECT c.ID_Compra AS id, c.Fecha_Transaccion AS fecha, "
           "COALESCE(p.Primer_Nombre_Proveedor, '') AS proveedor, "
           "i.Nombre_Insumo AS insumo, d.Cantidad AS cantidad, "
           "COALESCE(um.Descripcion, '') AS unidad, d.Costo_Adquisicion AS costo "
           "FROM compra c "
           "JOIN detallecompra d ON d.ID_Compra = c.ID_Compra "
           "JOIN insumo i ON i.ID_Insumo = d.ID_Insumo "
           "LEFT JOIN unidad_medida um ON i.ID_Unidad_M = um.ID_Unidad_M "
           "LEFT JOIN compra_relacional cr ON cr.ID_Compra = c.ID_Compra "
           "LEFT JOIN proveedor p ON p.RUC = cr.RUC")
    params = []
    if busqueda.strip():
        like = f"%{busqueda.strip()}%"
        sql += (" WHERE i.Nombre_Insumo LIKE ? OR "
                "p.Primer_Nombre_Proveedor LIKE ? OR c.Fecha_Transaccion LIKE ?")
        params = [like, like, like]
    sql += " ORDER BY c.Fecha_Transaccion DESC, c.ID_Compra DESC LIMIT ?"
    params.append(limite)
    return consultar(sql, params)


def _asegurar_insumo(nombre: str) -> int:
    """Devuelve el ID del insumo por nombre; si no existe, lo crea con valores
    por defecto (tipo y unidad del perecible)."""
    nombre = nombre.strip()
    fila = consultar("SELECT ID_Insumo i FROM insumo WHERE Nombre_Insumo = ? "
                     "COLLATE NOCASE", (nombre,))
    if fila:
        return fila[0]["i"]
    base = consultar("SELECT ID_Tipo, ID_Unidad_M FROM insumo "
                     "WHERE Nombre_Insumo = 'Insumos Perecibles'")
    if base:
        tipo, unidad = base[0]["ID_Tipo"], base[0]["ID_Unidad_M"]
    else:
        tipo = consultar("SELECT ID_Tipo FROM tipo_insumo LIMIT 1")[0]["ID_Tipo"]
        unidad = consultar("SELECT ID_Unidad_M FROM unidad_medida LIMIT 1")[0]["ID_Unidad_M"]
    return ejecutar("INSERT INTO insumo (Nombre_Insumo, ID_Tipo, ID_Unidad_M) "
                    "VALUES (?, ?, ?)", (nombre, tipo, unidad))


def _ruc_por_defecto(proveedor_ruc):
    if proveedor_ruc:
        return proveedor_ruc
    fila = consultar("SELECT RUC FROM proveedor LIMIT 1")
    return fila[0]["RUC"] if fila else None


def registrar_compra(fecha_iso, insumo, cantidad, costo, proveedor_ruc=None) -> int:
    """Crea la compra completa (3 tablas) y devuelve el id generado."""
    ins = _asegurar_insumo(insumo)
    ruc = _ruc_por_defecto(proveedor_ruc)
    temp = _temporada_de(fecha_iso)
    conn = conectar()
    try:
        cid = conn.execute("INSERT INTO compra (Fecha_Transaccion) VALUES (?)",
                           (fecha_iso,)).lastrowid
        conn.execute("INSERT INTO detallecompra (ID_Insumo, ID_Compra, Cantidad, "
                     "Costo_Adquisicion) VALUES (?, ?, ?, ?)",
                     (ins, cid, cantidad, costo))
        conn.execute("INSERT INTO compra_relacional (ID_Compra, RUC, ID_Temporada) "
                     "VALUES (?, ?, ?)", (cid, ruc, temp))
        conn.commit()
        return cid
    finally:
        conn.close()


def editar_compra(id_compra, fecha_iso, insumo, cantidad, costo, proveedor_ruc=None):
    """Actualiza una compra existente (fecha, insumo, cantidad, costo, proveedor)."""
    ins = _asegurar_insumo(insumo)
    conn = conectar()
    try:
        conn.execute("UPDATE compra SET Fecha_Transaccion = ? WHERE ID_Compra = ?",
                     (fecha_iso, id_compra))
        conn.execute("UPDATE detallecompra SET ID_Insumo = ?, Cantidad = ?, "
                     "Costo_Adquisicion = ? WHERE ID_Compra = ?",
                     (ins, cantidad, costo, id_compra))
        conn.execute("UPDATE compra_relacional SET RUC = ?, ID_Temporada = ? "
                     "WHERE ID_Compra = ?",
                     (_ruc_por_defecto(proveedor_ruc), _temporada_de(fecha_iso),
                      id_compra))
        conn.commit()
    finally:
        conn.close()


def eliminar_compra(id_compra) -> int:
    return eliminar("Compra", {"ID_Compra": id_compra})


def _temporada_de(fecha: str) -> int:
    fila = consultar("SELECT ID_Temporada i FROM temporada WHERE ? BETWEEN "
                     "Fecha_Inicio AND Fecha_Fin ORDER BY Fecha_Inicio LIMIT 1",
                     (fecha,))
    if fila:
        return fila[0]["i"]
    return consultar("SELECT ID_Temporada i FROM temporada ORDER BY Fecha_Fin "
                     "DESC LIMIT 1")[0]["i"]


def existe_fk(tabla_ref: str, columna_ref: str, valor) -> bool:
    fila = consultar(f"SELECT 1 FROM {tabla_ref} WHERE {columna_ref} = ? LIMIT 1",
                     (valor,))
    return bool(fila)


def valores_columna(tabla: str, columna: str) -> list:
    if tabla in ("Metodo_Pago", "metodo_pago"):
        return [f["Descripcion"] for f in consultar(
            "SELECT Descripcion FROM metodo_pago ORDER BY Descripcion")]
    filas = consultar(f"SELECT DISTINCT {columna} FROM {tabla} ORDER BY {columna}")
    return [f[0] for f in filas]


# =====================================================================
# Consultas de negocio (dashboard / reportes)
# =====================================================================
def rango_fechas() -> tuple:
    fila = consultar(
        """
        SELECT MIN(f) lo, MAX(f) hi FROM (
            SELECT MIN(Fecha_Entrega) f FROM racion
            UNION ALL SELECT MAX(Fecha_Entrega) FROM racion
            UNION ALL SELECT MIN(Fecha_Pago) FROM pago
            UNION ALL SELECT MAX(Fecha_Pago) FROM pago
            UNION ALL SELECT MIN(Fecha_Transaccion) FROM compra
            UNION ALL SELECT MAX(Fecha_Transaccion) FROM compra
        )
        """)[0]
    return fila["lo"], fila["hi"]


def _filtro(columna: str, desde, hasta) -> tuple:
    cond, params = [], []
    if desde:
        cond.append(f"{columna} >= ?"); params.append(desde)
    if hasta:
        cond.append(f"{columna} <= ?"); params.append(hasta)
    return (("WHERE " + " AND ".join(cond)) if cond else ""), params


def kpis(desde: str = None, hasta: str = None) -> dict:
    fp = _filtro("Fecha_Pago", desde, hasta)
    fc = _filtro("c.Fecha_Transaccion", desde, hasta)
    fr = _filtro("Fecha_Entrega", desde, hasta)
    ingresos = consultar(f"SELECT COALESCE(SUM(Monto_Menu),0) v FROM pago {fp[0]}",
                         fp[1])[0]["v"]
    gastos = consultar(
        f"SELECT COALESCE(SUM(d.Costo_Adquisicion),0) v FROM compra c "
        f"JOIN detallecompra d ON d.ID_Compra=c.ID_Compra {fc[0]}", fc[1])[0]["v"]
    raciones = consultar(f"SELECT COUNT(*) v FROM racion {fr[0]}", fr[1])[0]["v"]
    trabajadores = consultar("SELECT COUNT(*) v FROM trabajador WHERE ID_Estado=1")[0]["v"]
    return {"ingresos": ingresos, "gastos": gastos,
            "balance": ingresos - gastos, "raciones": raciones,
            "trabajadores": trabajadores}


def ingresos_gastos_por_mes(desde: str = None, hasta: str = None) -> list:
    fp = _filtro("Fecha_Pago", desde, hasta)
    fc = _filtro("c.Fecha_Transaccion", desde, hasta)
    sql = f"""
        SELECT mes, SUM(ingreso) ingreso, SUM(gasto) gasto FROM (
            SELECT strftime('%Y-%m', Fecha_Pago) mes, Monto_Menu ingreso, 0 gasto
            FROM pago {fp[0]}
            UNION ALL
            SELECT strftime('%Y-%m', c.Fecha_Transaccion) mes, 0 ingreso,
                   d.Costo_Adquisicion gasto
            FROM compra c JOIN detallecompra d ON d.ID_Compra=c.ID_Compra {fc[0]}
        ) GROUP BY mes ORDER BY mes
    """
    return consultar(sql, fp[1] + fc[1])


def raciones_por_mes(desde: str = None, hasta: str = None) -> list:
    fr = _filtro("Fecha_Entrega", desde, hasta)
    return consultar(f"SELECT strftime('%Y-%m', Fecha_Entrega) mes, COUNT(*) total "
                     f"FROM racion {fr[0]} GROUP BY mes ORDER BY mes", fr[1])


def top_trabajadores_raciones(limite: int = 10, desde: str = None,
                              hasta: str = None) -> list:
    fr = _filtro("rr.Fecha_Menu", desde, hasta)
    sql = f"""
        SELECT t.ID_Trabajador id_trabajador,
               {_APELLIDO} || ', ' || {_NOMBRE} AS nombre,
               COUNT(*) total
        FROM racion_relacional rr
        JOIN trabajador t ON t.ID_Trabajador = rr.ID_Trabajador
        {fr[0]}
        GROUP BY t.ID_Trabajador ORDER BY total DESC LIMIT ?
    """
    return consultar(sql, fr[1] + [limite])


def top_trabajadores_pagos(limite: int = 10, desde: str = None,
                           hasta: str = None) -> list:
    fp = _filtro("p.Fecha_Pago", desde, hasta)
    sql = f"""
        SELECT t.ID_Trabajador id_trabajador,
               {_APELLIDO} || ', ' || {_NOMBRE} AS nombre,
               COALESCE(SUM(p.Monto_Menu),0) total
        FROM pago p JOIN trabajador t ON t.ID_Trabajador = p.ID_Trabajador
        {fp[0]}
        GROUP BY t.ID_Trabajador ORDER BY total DESC LIMIT ?
    """
    return consultar(sql, fp[1] + [limite])


def uso_metodo_pago(desde: str = None, hasta: str = None) -> list:
    fp = _filtro("p.Fecha_Pago", desde, hasta)
    sql = f"""
        SELECT m.Descripcion Metodo_Pago, COUNT(*) n,
               COALESCE(SUM(p.Monto_Menu),0) total
        FROM pago p JOIN metodo_pago m ON m.ID_Metodo = p.ID_Metodo
        {fp[0]}
        GROUP BY m.Descripcion ORDER BY total DESC
    """
    return consultar(sql, fp[1])


# =====================================================================
# Quincenas (periodo_cobro)
# =====================================================================
def quincenas() -> list:
    filas = consultar("SELECT Codigo, Descripcion, Fecha_Inicio, Fecha_Fin "
                      "FROM periodo_cobro ORDER BY Fecha_Inicio")
    return [{"id": f["Codigo"], "descripcion": f["Descripcion"],
             "desde": f["Fecha_Inicio"], "hasta": f["Fecha_Fin"]} for f in filas]


def sugerir_quincena() -> tuple:
    qs = quincenas()
    desde = (date.fromisoformat(qs[-1]["hasta"]) + timedelta(days=1)) if qs else date.today()
    if desde.weekday() == 6:
        desde += timedelta(days=1)
    return desde.isoformat(), (desde + timedelta(days=13)).isoformat()


def crear_quincena(desde: str, hasta: str) -> dict:
    d1, d2 = date.fromisoformat(desde), date.fromisoformat(hasta)
    if d1 > d2:
        raise ValueError("La fecha de inicio es posterior a la de fin.")
    if (d2 - d1).days > 31:
        raise ValueError("Una quincena no puede durar más de un mes.")
    for q in quincenas():
        if desde <= q["hasta"] and hasta >= q["desde"]:
            raise ValueError(f"Las fechas se cruzan con la {q['descripcion']} "
                             f"del {q['desde']} al {q['hasta']}.")
    prefijo = d1.strftime("%Y%m")
    n = consultar("SELECT COUNT(*) n FROM periodo_cobro WHERE Codigo LIKE ?",
                  (f"{prefijo}Q%",))[0]["n"] + 1
    codigo = f"{prefijo}Q{n}"
    descripcion = f"Quincena {n} ({d1.strftime('%d/%m')}-{d2.strftime('%d/%m')})"
    ejecutar("INSERT INTO periodo_cobro (Descripcion, Codigo, Fecha_Inicio, "
             "Fecha_Fin) VALUES (?,?,?,?)", (descripcion, codigo, desde, hasta))
    return {"id": codigo, "descripcion": descripcion, "desde": desde, "hasta": hasta}


def _periodo_id(desde: str):
    fila = consultar("SELECT ID_Periodo i FROM periodo_cobro WHERE Fecha_Inicio=?",
                     (desde,))
    return fila[0]["i"] if fila else None


def inicio_quincena_vigente() -> str:
    """Fecha de inicio de la quincena que contiene HOY (o la más reciente ya
    empezada). Se usa para que un cambio de precio rija desde la quincena en
    curso —así se refleja de inmediato— sin tocar las quincenas ya pasadas."""
    hoy = date.today().isoformat()
    qs = quincenas()
    if not qs:
        return hoy
    for q in qs:
        if q["desde"] <= hoy <= q["hasta"]:
            return q["desde"]
    previas = [q for q in qs if q["desde"] <= hoy]
    return previas[-1]["desde"] if previas else qs[0]["desde"]


# =====================================================================
# Planilla de raciones
# =====================================================================
def raciones_quincena(desde: str, hasta: str) -> list:
    sql = f"""
        SELECT rr.ID_Trabajador id_trabajador,
               {_NOMBRE} Nombre, {_APELLIDO} Apellido, {_TEL} Telefono,
               e.Descripcion Estado,
               rr.Fecha_Menu Fecha, COUNT(*) Cantidad_Raciones
        FROM racion_relacional rr
        JOIN trabajador t ON t.ID_Trabajador = rr.ID_Trabajador
        JOIN estado_trabajador e ON e.ID_Estado = t.ID_Estado
        WHERE rr.Fecha_Menu BETWEEN ? AND ?
        GROUP BY rr.ID_Trabajador, rr.Fecha_Menu
    """
    return consultar(sql, (desde, hasta))


def fijar_racion(id_trabajador: str, fecha: str, cantidad) -> None:
    """Ajusta el nº de raciones de un trabajador en una fecha creando o
    borrando filas de `racion` (una por ración)."""
    cantidad = int(cantidad) if cantidad else 0
    conn = conectar()
    try:
        filas = conn.execute(
            "SELECT r.ID_Racion, r.ID_Pago FROM racion r JOIN racion_relacional rr "
            "ON rr.ID_Racion=r.ID_Racion WHERE rr.ID_Trabajador=? AND "
            "rr.Fecha_Menu=? ORDER BY (r.ID_Pago IS NOT NULL), r.ID_Racion",
            (id_trabajador, fecha)).fetchall()
        actuales = [r[0] for r in filas]
        pagadas = sum(1 for r in filas if r[1] is not None)
        n = len(actuales)
        if cantidad == n:
            return
        if cantidad < n:
            # No se pueden borrar raciones ya pagadas.
            if cantidad < pagadas:
                raise ValueError(
                    f"No puedes dejar menos de {pagadas} ese día: esas raciones ya "
                    "están pagadas. Corrige el pago primero.")
            quitar = actuales[:n - cantidad]  # primero las no pagadas
            marc = ",".join("?" * len(quitar))
            conn.execute(f"DELETE FROM racion_relacional WHERE ID_Racion IN ({marc})", quitar)
            conn.execute(f"DELETE FROM racion WHERE ID_Racion IN ({marc})", quitar)
            # Si el día quedó sin ninguna ración y el menú es el marcador
            # automático, se limpia (M3).
            resto = conn.execute("SELECT 1 FROM racion_relacional WHERE "
                                 "Fecha_Menu=? LIMIT 1", (fecha,)).fetchone()
            if not resto:
                conn.execute("DELETE FROM menu WHERE Fecha_Menu=? AND "
                             "Descripcion='Menú del día'", (fecha,))
        else:
            # Asegurar que exista el menú del día (FK de racion_relacional).
            if not conn.execute("SELECT 1 FROM menu WHERE Fecha_Menu=?", (fecha,)).fetchone():
                conn.execute("INSERT INTO menu (Fecha_Menu, Descripcion) VALUES "
                             "(?, 'Menú del día')", (fecha,))
            base = conn.execute("SELECT COALESCE(MAX(ID_Racion),0) m FROM racion").fetchone()[0]
            for k in range(cantidad - n):
                rid = base + 1 + k
                conn.execute("INSERT INTO racion (ID_Racion, Estado_Despacho, "
                             "Fecha_Entrega, ID_Pago) VALUES (?, 'Entregado', ?, NULL)",
                             (rid, fecha))
                conn.execute("INSERT INTO racion_relacional (ID_Racion, "
                             "ID_Trabajador, Fecha_Menu) VALUES (?,?,?)",
                             (rid, id_trabajador, fecha))
        conn.commit()
    finally:
        conn.close()


def buscar_trabajadores(texto: str, limite: int = 8) -> list:
    like = f"%{texto.strip()}%"
    sql = f"""
        SELECT t.ID_Trabajador id_trabajador, {_NOMBRE} Nombre,
               {_APELLIDO} Apellido, {_TEL} Telefono
        FROM trabajador t
        WHERE t.ID_Estado = 1
          AND ({_NOMBRE} || ' ' || {_APELLIDO} LIKE ?
               OR {_APELLIDO} || ' ' || {_NOMBRE} LIKE ?)
        ORDER BY t.Apellido_paterno, t.Primer_Nombre_Trabajador
        LIMIT ?
    """
    return consultar(sql, (like, like, limite))


# =====================================================================
# Trabajadores (alta con DNI, baja lógica)
# =====================================================================
def listar_trabajadores(busqueda: str = "", estado: str = None,
                        limite: int = 5000) -> list:
    cond, params = ["1=1"], []
    if busqueda.strip():
        like = f"%{busqueda.strip()}%"
        cond.append(f"({_NOMBRE} || ' ' || {_APELLIDO} LIKE ? OR {_TEL} LIKE ?)")
        params += [like, like]
    if estado:
        cond.append("e.Descripcion = ?"); params.append(estado)
    sql = f"""
        SELECT t.ID_Trabajador id_trabajador, {_NOMBRE} Nombre,
               {_APELLIDO} Apellido, {_TEL} Telefono, e.Descripcion Estado,
               t.Motivo_Baja, t.Fecha_Baja
        FROM trabajador t JOIN estado_trabajador e ON e.ID_Estado = t.ID_Estado
        WHERE {' AND '.join(cond)}
        ORDER BY t.Apellido_paterno, t.Apellido_materno, t.Primer_Nombre_Trabajador
        LIMIT ?
    """
    return consultar(sql, params + [limite])


def contar_por_estado() -> dict:
    filas = consultar("SELECT e.Descripcion d, COUNT(*) n FROM trabajador t "
                      "JOIN estado_trabajador e ON e.ID_Estado=t.ID_Estado GROUP BY 1")
    return {f["d"]: f["n"] for f in filas}


def telefono_existe(telefono: str, excluir_id: str = None):
    telefono = (telefono or "").strip()
    if not telefono:
        return None
    sql = (f"SELECT t.ID_Trabajador id_trabajador, {_NOMBRE} Nombre, "
           f"{_APELLIDO} Apellido, e.Descripcion Estado "
           "FROM tel_trabajador te "
           "JOIN trabajador t ON t.ID_Trabajador = te.ID_Trabajador "
           "JOIN estado_trabajador e ON e.ID_Estado = t.ID_Estado "
           "WHERE te.Telefono_Trabajador = ?")
    params = [telefono]
    if excluir_id:
        sql += " AND t.ID_Trabajador <> ?"; params.append(excluir_id)
    filas = consultar(sql + " LIMIT 1", params)
    return filas[0] if filas else None


def _partir_nombre(nombre: str):
    ns = nombre.strip().split()
    return ns[0], (" ".join(ns[1:]) if len(ns) > 1 else None)


def _partir_apellido(apellido: str):
    ap = apellido.strip().split()
    if len(ap) >= 2:
        return ap[0], " ".join(ap[1:])
    return ap[0], ap[0]


def generar_id_trabajador(nombre: str, apellido: str) -> str:
    """Genera el ID propio con el formato existente (001ALCO): correlativo
    siguiente + 2 letras del nombre + 2 del apellido."""
    mayor = consultar(
        "SELECT COALESCE(MAX(CAST(substr(ID_Trabajador, 1, "
        "length(ID_Trabajador)-4) AS INTEGER)), 0) v FROM trabajador")[0]["v"]
    iniciales = (nombre.strip()[:2] + apellido.strip()[:2]).upper()
    iniciales = iniciales.replace(" ", "X").ljust(4, "X")
    n = mayor + 1
    tid = f"{n:03d}{iniciales}"
    while existe_fk("trabajador", "ID_Trabajador", tid):
        n += 1
        tid = f"{n:03d}{iniciales}"
    return tid


def alta_trabajador(nombre: str, apellido: str, telefono: str,
                    precio: float = None) -> str:
    primer, segundo = _partir_nombre(nombre)
    paterno, materno = _partir_apellido(apellido)
    tid = generar_id_trabajador(nombre, apellido)
    conn = conectar()
    try:
        conn.execute(
            "INSERT INTO trabajador (ID_Trabajador, Primer_Nombre_Trabajador, "
            "Segundo_Nombre_Trabajador, Apellido_paterno, Apellido_materno, "
            "ID_Estado, Es_Nuevo) VALUES (?,?,?,?,?,1,1)",
            (tid, primer, segundo, paterno, materno))
        conn.execute("INSERT INTO tel_trabajador (ID_Trabajador, "
                     "Telefono_Trabajador) VALUES (?,?)", (tid, telefono.strip()))
        conn.commit()
    finally:
        conn.close()
    # Precio inicial del trabajador como su línea base (una sola fila limpia).
    if precio is not None:
        fijar_precio_trabajador(tid, precio, desde=_PRECIO_BASE_FECHA)
    return tid


def _actualizar_trabajador(datos: dict, dni: str) -> int:
    primer, segundo = _partir_nombre(datos["Nombre"])
    paterno, materno = _partir_apellido(datos["Apellido"])
    conn = conectar()
    try:
        conn.execute(
            "UPDATE trabajador SET Primer_Nombre_Trabajador=?, "
            "Segundo_Nombre_Trabajador=?, Apellido_paterno=?, Apellido_materno=? "
            "WHERE ID_Trabajador=?", (primer, segundo, paterno, materno, dni))
        conn.execute("DELETE FROM tel_trabajador WHERE ID_Trabajador=?", (dni,))
        conn.execute("INSERT INTO tel_trabajador (ID_Trabajador, "
                     "Telefono_Trabajador) VALUES (?,?)", (dni, datos["Telefono"].strip()))
        conn.commit()
        return 1
    finally:
        conn.close()


def dar_baja(id_trabajador: str, definitiva: bool, motivo: str, fecha: str) -> None:
    estado = _ESTADO_ID[ESTADO_DEFINITIVA if definitiva else ESTADO_TEMPORAL]
    ejecutar("UPDATE trabajador SET ID_Estado=?, Motivo_Baja=?, Fecha_Baja=? "
             "WHERE ID_Trabajador=?",
             (estado, (motivo or "").strip() or None, fecha, id_trabajador))


def reactivar_trabajador(id_trabajador: str) -> None:
    ejecutar("UPDATE trabajador SET ID_Estado=1, Motivo_Baja=NULL, Fecha_Baja=NULL "
             "WHERE ID_Trabajador=?", (id_trabajador,))


def deuda_trabajador(id_trabajador: str) -> float:
    """Total que el trabajador AÚN debe cobrar: suma de los saldos pendientes por
    quincena (mismo criterio que el panel de Raciones y la cobranza). No resta
    los saldos a favor, para que sea el monto realmente por cobrar."""
    return round(sum(d["saldo"] for d in deudas_pendientes(id_trabajador)), 2)


# =====================================================================
# Precio del menú (dos tarifas)
# =====================================================================
def precios_menu() -> dict:
    d = {r["Es_Nuevo"]: r["Precio"] for r in consultar(
        "SELECT Es_Nuevo, Precio FROM Precio_Menu")}
    return {"antiguo": d.get(0, 7.0), "nuevo": d.get(1, 8.0)}


def precio_por_defecto() -> float:
    """Precio sugerido para un trabajador nuevo (tarifa 'nuevo' base)."""
    return precios_menu()["nuevo"]


# ---------------------------------------------------------------
# Precio del menú POR TRABAJADOR, con fecha de vigencia.
# Cada trabajador tiene su precio a partir de una fecha; cambiarlo NO afecta las
# quincenas anteriores (rige desde la nueva fecha). Tabla de extensión, igual que
# Precio_Menu (no está en el diagrama original).
# ---------------------------------------------------------------
_precio_trab_listo = False
# Fecha base para el precio inicial (anterior a todos los datos): así ese precio
# rige para todo el historial del trabajador salvo que luego se cambie.
_PRECIO_BASE_FECHA = "2000-01-01"


def _asegurar_precio_trabajador():
    """Crea la tabla precio_trabajador si falta y la siembra una sola vez: a cada
    trabajador sin precio se le pone su tarifa actual (7/8) desde una fecha muy
    anterior, para que la cobranza histórica quede EXACTAMENTE igual que antes."""
    global _precio_trab_listo
    if _precio_trab_listo:
        return
    conn = conectar()
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS precio_trabajador (
                   ID_Trabajador VARCHAR(10) NOT NULL,
                   Precio        REAL        NOT NULL,
                   Fecha_Desde   TEXT        NOT NULL,
                   PRIMARY KEY (ID_Trabajador, Fecha_Desde))""")
        conn.execute(
            """INSERT INTO precio_trabajador (ID_Trabajador, Precio, Fecha_Desde)
               SELECT t.ID_Trabajador, pm.Precio, ?
               FROM trabajador t JOIN Precio_Menu pm ON pm.Es_Nuevo = t.Es_Nuevo
               WHERE NOT EXISTS (SELECT 1 FROM precio_trabajador p
                                 WHERE p.ID_Trabajador = t.ID_Trabajador)""",
            (_PRECIO_BASE_FECHA,))
        conn.commit()
        _precio_trab_listo = True
    finally:
        conn.close()


def precio_trabajador_en(id_trabajador: str, fecha: str) -> float:
    """Precio del menú vigente para el trabajador en esa fecha."""
    _asegurar_precio_trabajador()
    fila = consultar("SELECT Precio FROM precio_trabajador WHERE ID_Trabajador=? "
                     "AND Fecha_Desde <= ? ORDER BY Fecha_Desde DESC LIMIT 1",
                     (id_trabajador, fecha))
    return fila[0]["Precio"] if fila else precio_por_defecto()


def precio_trabajador_actual(id_trabajador: str) -> float:
    """Precio vigente hoy (para mostrarlo al editar el trabajador)."""
    return precio_trabajador_en(id_trabajador, date.today().isoformat())


def fijar_precio_trabajador(id_trabajador: str, precio: float, desde: str = None):
    """Fija el precio del trabajador a partir de `desde` (por defecto hoy). Las
    quincenas anteriores a esa fecha conservan el precio previo."""
    _asegurar_precio_trabajador()
    desde = desde or date.today().isoformat()
    ejecutar("INSERT INTO precio_trabajador (ID_Trabajador, Precio, Fecha_Desde) "
             "VALUES (?,?,?) ON CONFLICT(ID_Trabajador, Fecha_Desde) "
             "DO UPDATE SET Precio=excluded.Precio",
             (id_trabajador, round(float(precio), 2), desde))


# =====================================================================
# Cobranza por quincena
# =====================================================================
def cobranza_quincena(desde: str, hasta: str, fin_ventana: str) -> list:
    _asegurar_precio_trabajador()
    # Precio vigente para el trabajador al INICIO de la quincena (no el actual):
    # así, cambiar el precio hoy no altera lo que se debía en quincenas pasadas.
    precio = ("(SELECT pt.Precio FROM precio_trabajador pt "
              "WHERE pt.ID_Trabajador = t.ID_Trabajador AND pt.Fecha_Desde <= ? "
              "ORDER BY pt.Fecha_Desde DESC LIMIT 1)")
    sql = f"""
        WITH consumo AS (
            SELECT rr.ID_Trabajador dni, COUNT(*) raciones
            FROM racion_relacional rr
            WHERE rr.Fecha_Menu BETWEEN ? AND ?
            GROUP BY rr.ID_Trabajador
        ),
        pagos AS (
            SELECT ID_Trabajador dni, SUM(Monto_Menu) pagado
            FROM pago WHERE Fecha_Pago >= ? AND Fecha_Pago < ?
            GROUP BY ID_Trabajador
        )
        SELECT t.ID_Trabajador id_trabajador, {_NOMBRE} Nombre,
               {_APELLIDO} Apellido, {_TEL} Telefono,
               COALESCE(c.raciones,0) raciones,
               ROUND(COALESCE(c.raciones,0)*{precio},2) a_pagar,
               ROUND(COALESCE(p.pagado,0),2) pagado,
               ROUND(COALESCE(c.raciones,0)*{precio} - COALESCE(p.pagado,0),2) saldo
        FROM trabajador t
             LEFT JOIN consumo c ON c.dni = t.ID_Trabajador
             LEFT JOIN pagos   p ON p.dni = t.ID_Trabajador
        WHERE c.dni IS NOT NULL OR p.dni IS NOT NULL
        ORDER BY saldo DESC, t.Apellido_paterno, t.Primer_Nombre_Trabajador
    """
    # Parámetros en orden de aparición: consumo(desde,hasta), pagos(desde,fin),
    # a_pagar(desde), saldo(desde).
    return consultar(sql, (desde, hasta, desde, fin_ventana, desde, desde))


def cobranza_trabajador(id_trabajador: str, desde: str, hasta: str,
                        fin_ventana: str) -> dict:
    """Resumen de UN trabajador en UNA quincena (mismo criterio que la cobranza):
    raciones, precio vigente, a pagar, pagado y saldo."""
    _asegurar_precio_trabajador()
    n = consultar("SELECT COUNT(*) c FROM racion_relacional WHERE ID_Trabajador=? "
                  "AND Fecha_Menu BETWEEN ? AND ?",
                  (id_trabajador, desde, hasta))[0]["c"]
    pagado = consultar("SELECT COALESCE(SUM(Monto_Menu),0) v FROM pago "
                       "WHERE ID_Trabajador=? AND Fecha_Pago>=? AND Fecha_Pago<?",
                       (id_trabajador, desde, fin_ventana))[0]["v"]
    precio = precio_trabajador_en(id_trabajador, desde)
    a_pagar = round(n * precio, 2)
    return {"raciones": n, "precio": precio, "a_pagar": a_pagar,
            "pagado": round(pagado, 2), "saldo": round(a_pagar - pagado, 2)}


def deudas_pendientes(id_trabajador: str) -> list:
    """Quincenas donde el trabajador AÚN debe (saldo > 0), con sus fechas y monto.
    Ordenadas de la más antigua a la más reciente."""
    _asegurar_precio_trabajador()
    qs = quincenas()
    rac = {r["cod"]: r["n"] for r in consultar(
        "SELECT pc.Codigo cod, COUNT(*) n FROM racion_relacional rr "
        "JOIN periodo_cobro pc ON rr.Fecha_Menu BETWEEN pc.Fecha_Inicio AND pc.Fecha_Fin "
        "WHERE rr.ID_Trabajador=? GROUP BY pc.Codigo", (id_trabajador,))}
    pagos = consultar("SELECT Fecha_Pago f, Monto_Menu m FROM pago "
                      "WHERE ID_Trabajador=?", (id_trabajador,))
    out = []
    for i, q in enumerate(qs):
        fin = qs[i + 1]["desde"] if i + 1 < len(qs) else "9999-12-31"
        n = rac.get(q["id"], 0)
        pagado = sum(p["m"] for p in pagos if q["desde"] <= p["f"] < fin)
        if n == 0 and pagado == 0:
            continue
        saldo = round(n * precio_trabajador_en(id_trabajador, q["desde"]) - pagado, 2)
        if saldo > 0.005:
            out.append({"id": q["id"], "descripcion": q["descripcion"],
                        "desde": q["desde"], "hasta": q["hasta"], "saldo": saldo})
    return out


def registrar_pago(id_trabajador: str, fecha: str, metodo: str, monto: float,
                   ini_ventana: str, fin_ventana: str) -> int:
    periodo = _periodo_id(ini_ventana)
    met = consultar("SELECT ID_Metodo i FROM metodo_pago WHERE Descripcion=?",
                    (metodo,))
    met_id = met[0]["i"] if met else consultar(
        "SELECT ID_Metodo i FROM metodo_pago LIMIT 1")[0]["i"]
    # Precio vigente al inicio de la quincena (coherente con la cobranza).
    precio = precio_trabajador_en(id_trabajador, ini_ventana)
    conn = conectar()
    try:
        pid = conn.execute(
            "INSERT INTO pago (Monto_Menu, Monto_Envio, Fecha_Pago, ID_Metodo, "
            "ID_Periodo, ID_Trabajador) VALUES (?,0,?,?,?,?)",
            (monto, fecha, met_id, periodo, id_trabajador)).lastrowid
        # Marca como pagadas las raciones de la quincena que cubre el monto.
        cubre = int(round(monto / precio)) if precio else 0
        if cubre > 0:
            ids = [r[0] for r in conn.execute(
                "SELECT r.ID_Racion FROM racion r JOIN racion_relacional rr "
                "ON rr.ID_Racion=r.ID_Racion WHERE rr.ID_Trabajador=? AND "
                "rr.Fecha_Menu BETWEEN ? AND ? AND r.ID_Pago IS NULL "
                "ORDER BY rr.Fecha_Menu LIMIT ?",
                (id_trabajador, ini_ventana, hasta_de(ini_ventana), cubre)).fetchall()]
            if ids:
                marc = ",".join("?" * len(ids))
                conn.execute(f"UPDATE racion SET ID_Pago=? WHERE ID_Racion IN ({marc})",
                             [pid] + ids)
        conn.commit()
        return pid
    finally:
        conn.close()


def hasta_de(desde: str) -> str:
    fila = consultar("SELECT Fecha_Fin f FROM periodo_cobro WHERE Fecha_Inicio=?",
                     (desde,))
    return fila[0]["f"] if fila else desde


# =====================================================================
# Menú semanal
# =====================================================================
def platos_semana(desde: str, hasta: str) -> dict:
    filas = consultar("SELECT Fecha_Menu, Descripcion FROM menu WHERE "
                      "Fecha_Menu BETWEEN ? AND ?", (desde, hasta))
    return {f["Fecha_Menu"]: f["Descripcion"] for f in filas}


def fijar_plato(fecha: str, plato: str) -> None:
    plato = (plato or "").strip()
    if not plato:
        # Si hay raciones ese día no se puede borrar el menú (FK); se deja
        # un marcador genérico.
        hay = consultar("SELECT 1 FROM racion_relacional WHERE Fecha_Menu=? LIMIT 1",
                        (fecha,))
        if hay:
            ejecutar("UPDATE menu SET Descripcion='Menú del día' WHERE Fecha_Menu=?",
                     (fecha,))
        else:
            ejecutar("DELETE FROM menu WHERE Fecha_Menu=?", (fecha,))
        return
    ejecutar("INSERT INTO menu (Fecha_Menu, Descripcion) VALUES (?,?) "
             "ON CONFLICT(Fecha_Menu) DO UPDATE SET Descripcion=excluded.Descripcion",
             (fecha, plato))


def platos_conocidos() -> list:
    return [f["Descripcion"] for f in consultar(
        "SELECT DISTINCT Descripcion FROM menu WHERE Descripcion<>'Menú del día' "
        "ORDER BY Descripcion")]


if __name__ == "__main__":
    print("Rango de fechas:", rango_fechas())
    print("KPIs:", dict(kpis()))
