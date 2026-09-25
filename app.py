# -*- coding: utf-8 -*-
"""
Kelly's Food - Programa de escritorio
=====================================
Aplicación de gestión para el negocio "Kelly's Food" (venta de comida a
trabajadores de una empresa). Curso Base de Datos Avanzada - UNT.

La base de datos SQLite `kellys_food.db` ya viene cargada. Si no existe, se
construye automáticamente al iniciar a partir de los .sql de datos_sql/.

Funciones:
  * Dashboard con KPIs y gráficos
  * CRUD de las tablas (Trabajadores, Raciones, Pagos, Compras, Menú, etc.)
  * Consultas y reportes con exportación a CSV/Excel

Uso:
    py app.py
"""

import os
import sys

import customtkinter as ctk

import db
from ui import estilos
from ui.crud_view import VistaCRUD
from ui.dashboard import Dashboard
from ui.consultas import Consultas
from ui.raciones_view import VistaRaciones
from ui.trabajadores_view import VistaTrabajadores
from ui.menu_view import VistaMenu
from ui.pagos_view import VistaPagos
from ui.compras_view import VistaCompras


def asegurar_bd():
    """Si falta la BD, la construye antes de arrancar la interfaz."""
    if not os.path.exists(db.RUTA_DB):
        print("No existe kellys_food.db; construyéndola…")
        import construir_bd
        construir_bd.construir()


class App(ctk.CTk):
    ANCHO_MENU = 230

    def __init__(self):
        super().__init__()
        self.title(f"{estilos.TITULO_APP} — Gestión")
        self.geometry("1180x720")
        self.minsize(980, 620)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._construir_menu()
        self._area = ctk.CTkFrame(self, fg_color=estilos.FONDO, corner_radius=0)
        self._area.grid(row=0, column=1, sticky="nsew")
        self._area.grid_rowconfigure(0, weight=1)
        self._area.grid_columnconfigure(0, weight=1)

        self._vista_actual = None
        self._cache = {}
        self.mostrar("dashboard")

    # ------------------------------------------------------------------
    def _construir_menu(self):
        menu = ctk.CTkFrame(self, width=self.ANCHO_MENU, corner_radius=0,
                            fg_color=estilos.VERDE_OSCURO)
        menu.grid(row=0, column=0, sticky="nsew")
        menu.grid_propagate(False)
        menu.grid_rowconfigure(20, weight=1)

        ctk.CTkLabel(menu, text="🍽  Kelly's Food",
                     font=estilos.fuente(20, "bold"),
                     text_color="#FFFFFF").grid(
            row=0, column=0, sticky="w", padx=20, pady=(22, 2))
        ctk.CTkLabel(menu, text="Gestión del negocio",
                     font=estilos.fuente(11), text_color="#CDE6D8").grid(
            row=1, column=0, sticky="w", padx=20, pady=(0, 18))

        self._botones = {}
        items = [
            ("dashboard", "📊  Dashboard"),
            ("Trabajador", "👤  Trabajadores"),
            ("Racion", "🍲  Raciones"),
            ("Pago", "💵  Pagos"),
            ("Compra", "🧾  Compras"),
            ("Menu", "📅  Menú"),
            ("Metodo_Pago", "💳  Métodos de pago"),
            ("Periodo_Cobro", "🗓  Períodos de cobro"),
            ("consultas", "🔎  Consultas / Reportes"),
        ]
        for i, (clave, texto) in enumerate(items, start=2):
            b = ctk.CTkButton(
                menu, text=texto, anchor="w", height=42,
                corner_radius=8, fg_color="transparent",
                font=estilos.fuente(14), text_color="#EAF2ED",
                hover_color=estilos.VERDE, command=lambda c=clave: self.mostrar(c),
            )
            b.grid(row=i, column=0, sticky="ew", padx=12, pady=2)
            self._botones[clave] = b

        # Pie: selector de tema
        pie = ctk.CTkFrame(menu, fg_color="transparent")
        pie.grid(row=21, column=0, sticky="ew", padx=12, pady=16)
        ctk.CTkLabel(pie, text="Apariencia", font=estilos.fuente(11),
                     text_color="#CDE6D8").pack(anchor="w", padx=4)
        self.sel_tema = ctk.CTkSegmentedButton(
            pie, values=["Oscuro", "Claro"], command=self._cambiar_tema)
        self.sel_tema.set("Oscuro")
        self.sel_tema.pack(fill="x", pady=(4, 0))

    # ------------------------------------------------------------------
    def _cambiar_tema(self, valor):
        ctk.set_appearance_mode("Dark" if valor == "Oscuro" else "Light")
        estilos.estilizar_treeview()
        # Reconstruir vistas cacheadas para que tomen los nuevos colores.
        actual = self._clave_actual
        self._cache.clear()
        if self._vista_actual:
            self._vista_actual.destroy()
            self._vista_actual = None
        self.mostrar(actual)

    def mostrar(self, clave):
        self._clave_actual = clave
        for c, b in self._botones.items():
            b.configure(fg_color=estilos.VERDE if c == clave else "transparent")

        if self._vista_actual is not None:
            self._vista_actual.grid_forget()

        if clave not in self._cache:
            self._cache[clave] = self._crear_vista(clave)
        vista = self._cache[clave]
        vista.grid(row=0, column=0, sticky="nsew", padx=18, pady=18)
        self._vista_actual = vista

        # Las vistas dinámicas se refrescan al mostrarse.
        if hasattr(vista, "refrescar"):
            vista.refrescar()

    def _crear_vista(self, clave):
        if clave == "dashboard":
            return Dashboard(self._area)
        if clave == "consultas":
            return Consultas(self._area)
        if clave == "Racion":
            return VistaRaciones(self._area)
        if clave == "Trabajador":
            return VistaTrabajadores(self._area)
        if clave == "Menu":
            return VistaMenu(self._area)
        if clave == "Pago":
            return VistaPagos(self._area)
        if clave == "Compra":
            return VistaCompras(self._area)
        return VistaCRUD(self._area, clave)


def main():
    asegurar_bd()
    estilos.aplicar_tema_inicial()
    app = App()
    app.mainloop()


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as e:
        print("ERROR:", e)
        sys.exit(1)
