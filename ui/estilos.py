# -*- coding: utf-8 -*-
"""
Kelly's Food - Paleta de marca y estilos compartidos
====================================================
Centraliza colores, fuentes y el estilo del ttk.Treeview para que toda la
aplicación se vea consistente y elegante, tanto en modo claro como oscuro.
"""

import tkinter.font as tkfont
from tkinter import ttk

import customtkinter as ctk

# --- Paleta de marca "Kelly's Food" (verde comida + ámbar cálido) ----------
VERDE = "#2E7D5B"          # primario
VERDE_OSCURO = "#245F46"
VERDE_HOVER = "#3A9E73"
AMBAR = "#E8A33D"          # acento
AMBAR_HOVER = "#F2B457"
ROJO = "#C0504D"           # negativos / eliminar
ROJO_HOVER = "#D46662"

# Colores dependientes del tema (claro, oscuro)
FONDO = ("#F4F1EA", "#1C2321")          # crema / verde-negro
SUPERFICIE = ("#FFFFFF", "#28322E")     # tarjetas / paneles
BORDE = ("#E0DACd", "#3A463F")
TEXTO = ("#20302A", "#EAF2ED")
TEXTO_TENUE = ("#6B7A72", "#9DB0A6")

# Colores de estado para KPIs
POSITIVO = "#2E7D5B"
NEGATIVO = "#C0504D"

TITULO_APP = "Kelly's Food"


def _lado(par, modo):
    """Devuelve el color del par (claro, oscuro) según el modo actual."""
    return par[1] if modo == "Dark" else par[0]


def fuente(size=13, weight="normal"):
    return ctk.CTkFont(family="Segoe UI", size=size, weight=weight)


def aplicar_tema_inicial():
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("green")


def estilizar_treeview(modo: str | None = None):
    """Aplica al ttk.Treeview colores acordes al tema de CustomTkinter."""
    if modo is None:
        modo = ctk.get_appearance_mode()

    fondo = _lado(SUPERFICIE, modo)
    texto = _lado(TEXTO, modo)
    borde = _lado(BORDE, modo)
    encabezado = VERDE_OSCURO if modo == "Dark" else VERDE
    seleccion = VERDE_HOVER

    style = ttk.Style()
    style.theme_use("default")
    style.configure(
        "Kelly.Treeview",
        background=fondo,
        foreground=texto,
        fieldbackground=fondo,
        borderwidth=0,
        rowheight=30,
        font=("Segoe UI", 11),
    )
    style.map(
        "Kelly.Treeview",
        background=[("selected", seleccion)],
        foreground=[("selected", "#FFFFFF")],
    )
    style.configure(
        "Kelly.Treeview.Heading",
        background=encabezado,
        foreground="#FFFFFF",
        relief="flat",
        font=("Segoe UI Semibold", 11),
        padding=(8, 6),
    )
    style.map(
        "Kelly.Treeview.Heading",
        background=[("active", VERDE_HOVER)],
    )
    # Scrollbars discretas
    style.configure(
        "Kelly.Vertical.TScrollbar",
        background=borde, troughcolor=fondo, borderwidth=0, arrowsize=12,
    )
    return style
