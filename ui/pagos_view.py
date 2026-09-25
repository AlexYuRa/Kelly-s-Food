# -*- coding: utf-8 -*-
"""
Kelly's Food - Pagos y cobranza por quincena
============================================
La pantalla de cobrar: se elige la quincena y el sistema calcula por
trabajador cuánto consumió (raciones × precio vigente), cuánto pagó y cuánto
debe. Los que deben salen primero y en rojo. Seleccionando a alguien se le
registra el pago con dos clics. También se cambia aquí el precio de la ración.
"""

from datetime import date, datetime

from tkinter import ttk, messagebox

import customtkinter as ctk

import db
from ui import estilos

IID_TOTAL = "__total__"


def _soles(v):
    return f"S/ {v:,.2f}"


class VistaPagos(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.quincenas = db.quincenas()
        if not self.quincenas:
            ctk.CTkLabel(self, text="No hay períodos de cobro definidos.",
                         font=estilos.fuente(14)).pack(pady=40)
            return
        self._etiquetas = [f"{q['desde'][:4]} · {q['descripcion']}"
                           for q in self.quincenas]
        self._idx = self._indice_hoy()
        self._filas = []
        self._sel = None

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._construir_encabezado()
        self._construir_tabla()
        self._construir_panel_pago()
        self._cargar()

    # ------------------------------------------------------------------
    def _construir_encabezado(self):
        ctk.CTkLabel(self, text="Pagos y cobranza",
                     font=estilos.fuente(24, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=4, pady=(4, 8))

        barra = ctk.CTkFrame(self, corner_radius=12)
        barra.grid(row=1, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 10))
        fila = ctk.CTkFrame(barra, fg_color="transparent")
        fila.pack(fill="x", padx=12, pady=(10, 4))

        ctk.CTkButton(fila, text="◀", width=36, height=34,
                      command=lambda: self._mover(-1)).pack(side="left")
        self.combo_q = ctk.CTkComboBox(fila, values=self._etiquetas, width=300,
                                       height=34, command=self._elegir_quincena)
        self.combo_q.pack(side="left", padx=6)
        ctk.CTkButton(fila, text="▶", width=36, height=34,
                      command=lambda: self._mover(1)).pack(side="left")
        ctk.CTkButton(fila, text="Ir a hoy", width=80, height=34,
                      fg_color="transparent", border_width=1,
                      command=self._ir_a_hoy).pack(side="left", padx=(10, 0))

        self.e_filtro = ctk.CTkEntry(fila, width=200, height=34,
                                     placeholder_text="Buscar por nombre…")
        self.e_filtro.pack(side="right")
        self.e_filtro.bind("<KeyRelease>", lambda e: self._llenar())

        fila2 = ctk.CTkFrame(barra, fg_color="transparent")
        fila2.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(fila2, text="El precio del menú se define por trabajador "
                                 "(en «Trabajadores»).",
                     font=estilos.fuente(11),
                     text_color=estilos.TEXTO_TENUE).pack(side="left")
        self.chk_deuda = ctk.CTkCheckBox(fila2, text="Mostrar solo los que deben",
                                         font=estilos.fuente(12),
                                         command=self._llenar)
        self.chk_deuda.pack(side="right")

    # ------------------------------------------------------------------
    def _construir_tabla(self):
        cont = ctk.CTkFrame(self, corner_radius=12)
        cont.grid(row=2, column=0, sticky="nsew", padx=(4, 10))
        cont.grid_rowconfigure(0, weight=1)
        cont.grid_columnconfigure(0, weight=1)

        estilos.estilizar_treeview()
        cols = ("nombre", "raciones", "a_pagar", "pagado", "saldo", "situacion")
        self.tree = ttk.Treeview(cont, columns=cols, show="headings",
                                 style="Kelly.Treeview", selectmode="browse")
        for col, etiqueta, ancho, ancla in (
                ("nombre", "Trabajador", 180, "w"),
                ("raciones", "Raciones", 75, "center"),
                ("a_pagar", "A pagar", 95, "e"),
                ("pagado", "Pagó", 95, "e"),
                ("saldo", "Saldo", 95, "e"),
                ("situacion", "Situación", 85, "center")):
            self.tree.heading(col, text=etiqueta)
            self.tree.column(col, width=ancho, anchor=ancla)

        vsb = ttk.Scrollbar(cont, orient="vertical", command=self.tree.yview,
                            style="Kelly.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=6)
        vsb.grid(row=0, column=1, sticky="ns", pady=6, padx=(0, 6))

        modo = ctk.get_appearance_mode()
        self.tree.tag_configure("par", background=estilos._lado(estilos.FONDO, modo))
        self.tree.tag_configure("debe", foreground=estilos.ROJO_HOVER)
        self.tree.tag_configure("totales", background=estilos.VERDE_OSCURO,
                                foreground="#FFFFFF",
                                font=("Segoe UI Semibold", 11))
        self.tree.bind("<<TreeviewSelect>>", self._al_seleccionar)

        self.lbl_resumen = ctk.CTkLabel(cont, text="", font=estilos.fuente(11),
                                        text_color=estilos.TEXTO_TENUE)
        self.lbl_resumen.grid(row=1, column=0, columnspan=2, sticky="w",
                              padx=10, pady=(0, 6))

    # ------------------------------------------------------------------
    def _construir_panel_pago(self):
        panel = ctk.CTkScrollableFrame(self, corner_radius=12,
                                       label_text="Registrar pago")
        panel.grid(row=2, column=1, sticky="nsew", padx=(0, 4))
        panel.grid_columnconfigure(0, weight=1)

        self.lbl_quien = ctk.CTkLabel(panel, text="Elige a alguien en la lista",
                                      font=estilos.fuente(14, "bold"),
                                      wraplength=210, justify="left")
        self.lbl_quien.grid(sticky="ew", padx=6, pady=(10, 0))
        self.lbl_deuda = ctk.CTkLabel(panel, text="", font=estilos.fuente(12),
                                      wraplength=210, justify="left",
                                      text_color=estilos.TEXTO_TENUE)
        self.lbl_deuda.grid(sticky="ew", padx=6, pady=(2, 8))

        ctk.CTkLabel(panel, text="Monto (S/)", anchor="w",
                     font=estilos.fuente(12, "bold")).grid(sticky="ew", padx=6)
        self.e_monto = ctk.CTkEntry(panel, height=34)
        self.e_monto.grid(sticky="ew", padx=6, pady=(2, 8))

        ctk.CTkLabel(panel, text="Método de pago", anchor="w",
                     font=estilos.fuente(12, "bold")).grid(sticky="ew", padx=6)
        metodos = db.valores_columna("Metodo_Pago", "Metodo_Pago")
        self.seg_metodo = ctk.CTkSegmentedButton(panel, values=metodos, height=34)
        if metodos:
            self.seg_metodo.set(metodos[0])
        self.seg_metodo.grid(sticky="ew", padx=6, pady=(2, 8))

        ctk.CTkLabel(panel, text="Fecha (dd/mm/aaaa)", anchor="w",
                     font=estilos.fuente(12, "bold")).grid(sticky="ew", padx=6)
        self.e_fecha = ctk.CTkEntry(panel, height=34)
        self.e_fecha.grid(sticky="ew", padx=6, pady=(2, 10))

        self.btn_pagar = ctk.CTkButton(panel, text="💾 Registrar pago",
                                       height=38, command=self.registrar)
        self.btn_pagar.grid(sticky="ew", padx=6, pady=(0, 6))

        self.lbl_msj = ctk.CTkLabel(panel, text="", font=estilos.fuente(11),
                                    wraplength=210, justify="left",
                                    text_color=estilos.TEXTO_TENUE)
        self.lbl_msj.grid(sticky="ew", padx=6, pady=(2, 10))
        self._reflejar_seleccion()

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------
    def refrescar(self):
        if not getattr(self, "quincenas", None):
            return
        # Releer las quincenas (pueden haberse creado desde Raciones).
        actual = self.quincenas[self._idx]["id"]
        self.quincenas = db.quincenas()
        self._etiquetas = [f"{q['desde'][:4]} · {q['descripcion']}"
                           for q in self.quincenas]
        self.combo_q.configure(values=self._etiquetas)
        self._idx = next((i for i, q in enumerate(self.quincenas)
                          if q["id"] == actual), self._indice_hoy())
        self._cargar()

    def _ventana(self):
        """(desde, hasta, fin_ventana): los pagos de la quincena cuentan
        hasta el inicio de la siguiente."""
        q = self.quincenas[self._idx]
        if self._idx + 1 < len(self.quincenas):
            fin = self.quincenas[self._idx + 1]["desde"]
        else:
            fin = "9999-12-31"
        return q["desde"], q["hasta"], fin

    def _cargar(self):
        q = self.quincenas[self._idx]
        self.combo_q.set(self._etiquetas[self._idx])
        desde, hasta, fin = self._ventana()
        self._filas = db.cobranza_quincena(desde, hasta, fin)
        self._sel = None
        self._llenar()
        self._reflejar_seleccion()

    def _llenar(self):
        self.tree.delete(*self.tree.get_children())
        filtro = self.e_filtro.get().strip().lower()
        solo_deuda = bool(self.chk_deuda.get())

        visibles = 0
        t_rac = t_pagar = t_pagado = t_saldo = 0
        deudores = 0
        for f in self._filas:
            nombre = f"{f['Nombre']} {f['Apellido']}"
            if filtro and filtro not in nombre.lower():
                continue
            debe = f["saldo"] > 0.005
            if solo_deuda and not debe:
                continue
            situacion = "Debe" if debe else ("A favor" if f["saldo"] < -0.005
                                             else "Al día")
            tags = ["par"] if visibles % 2 else []
            if debe:
                tags.append("debe")
                deudores += 1
            self.tree.insert(
                "", "end", iid=f["id_trabajador"],
                values=(nombre, f["raciones"], _soles(f["a_pagar"]),
                        _soles(f["pagado"]), _soles(f["saldo"]), situacion),
                tags=tuple(tags))
            visibles += 1
            t_rac += f["raciones"]
            t_pagar += f["a_pagar"]
            t_pagado += f["pagado"]
            t_saldo += f["saldo"]

        self.tree.insert("", "end", iid=IID_TOTAL, tags=("totales",),
                         values=("TOTAL", t_rac, _soles(t_pagar),
                                 _soles(t_pagado), _soles(t_saldo), ""))
        self.lbl_resumen.configure(
            text=f"{visibles} trabajador(es) · {deudores} con deuda · "
                 f"por cobrar {_soles(max(t_saldo, 0))}")

    # ------------------------------------------------------------------
    # Selección y registro de pago
    # ------------------------------------------------------------------
    def _al_seleccionar(self, _e=None):
        sel = self.tree.selection()
        if not sel or sel[0] == IID_TOTAL:
            return
        self._sel = sel[0]
        self._reflejar_seleccion()

    def _fila_sel(self):
        for f in self._filas:
            if f["id_trabajador"] == self._sel:
                return f
        return None

    def _reflejar_seleccion(self):
        f = self._fila_sel()
        if not f:
            self.lbl_quien.configure(text="Elige a alguien en la lista")
            self.lbl_deuda.configure(text="")
            self.btn_pagar.configure(state="disabled")
            return
        self.btn_pagar.configure(state="normal")
        self.lbl_quien.configure(text=f"{f['Nombre']} {f['Apellido']}")
        if f["saldo"] > 0.005:
            texto = f"Debe {_soles(f['saldo'])} de esta quincena."
        elif f["saldo"] < -0.005:
            texto = f"Tiene {_soles(-f['saldo'])} a favor."
        else:
            texto = "Está al día en esta quincena."
        self.lbl_deuda.configure(text=texto)

        self.e_monto.delete(0, "end")
        if f["saldo"] > 0.005:
            self.e_monto.insert(0, f"{f['saldo']:.2f}")
        desde, _hasta, fin = self._ventana()
        hoy = date.today().isoformat()
        fecha = hoy if desde <= hoy < fin else max(desde, min(hoy, _hasta))
        self.e_fecha.delete(0, "end")
        self.e_fecha.insert(0, datetime.strptime(fecha, "%Y-%m-%d").strftime("%d/%m/%Y"))

    def registrar(self):
        f = self._fila_sel()
        if not f:
            return
        try:
            monto = round(float(self.e_monto.get().strip().replace(",", ".")), 2)
        except ValueError:
            monto = -1
        if monto <= 0:
            self._msj("⚠ Escribe el monto en soles, por ejemplo 25.50.",
                      error=True)
            return
        try:
            fecha = datetime.strptime(self.e_fecha.get().strip(),
                                      "%d/%m/%Y").date().isoformat()
        except ValueError:
            self._msj("⚠ La fecha debe ser dd/mm/aaaa, por ejemplo "
                      f"{date.today().strftime('%d/%m/%Y')}.", error=True)
            return
        desde, _hasta, fin = self._ventana()
        if not (desde <= fecha < fin):
            self._msj(f"⚠ Para que cuente en esta quincena, la fecha debe estar "
                      f"entre {self._ddmma(desde)} y {self._ddmma(fin, -1)}.",
                      error=True)
            return
        metodo = self.seg_metodo.get()
        if not metodo:
            self._msj("⚠ Elige el método de pago.", error=True)
            return
        # Aviso si el monto supera el saldo o si no hay nada pendiente (adelanto).
        saldo = f["saldo"]
        if monto > saldo + 0.005:
            exceso = monto - max(saldo, 0)
            if saldo > 0.005:
                pregunta = (f"El monto ({_soles(monto)}) es mayor que lo que debe "
                            f"({_soles(saldo)}).\nQuedarán {_soles(exceso)} a favor. "
                            "¿Registrar de todas formas?")
            else:
                pregunta = (f"{f['Nombre']} {f['Apellido']} no tiene saldo "
                            f"pendiente en esta quincena.\nQuedarán {_soles(exceso)} "
                            "a favor. ¿Registrar el pago igual?")
            if not messagebox.askyesno("Confirmar pago", pregunta):
                return
        nombre = f"{f['Nombre']} {f['Apellido']}"
        try:
            db.registrar_pago(f["id_trabajador"], fecha, metodo, monto, desde, fin)
        except Exception as e:
            self._msj(f"⚠ No se pudo registrar: {e}", error=True)
            return

        sel = self._sel
        desde_, hasta_, fin_ = self._ventana()
        self._filas = db.cobranza_quincena(desde_, hasta_, fin_)
        self._llenar()
        self._sel = sel
        if self.tree.exists(sel):
            self.tree.selection_set(sel)
            self.tree.see(sel)
        self._reflejar_seleccion()
        self._msj(f"Pago de {_soles(monto)} de {nombre} registrado ({metodo}).")

    @staticmethod
    def _ddmma(iso, ajuste_dias=0):
        from datetime import timedelta
        f = date.fromisoformat(iso if iso != "9999-12-31" else "9999-12-30")
        return (f + timedelta(days=ajuste_dias)).strftime("%d/%m/%Y")

    def _msj(self, texto, error=False):
        self.lbl_msj.configure(
            text=texto, text_color=estilos.ROJO if error else estilos.VERDE_HOVER)

    # ------------------------------------------------------------------
    # Navegación de quincenas
    # ------------------------------------------------------------------
    def _indice_hoy(self):
        hoy = date.today().isoformat()
        for i, q in enumerate(self.quincenas):
            if q["desde"] <= hoy <= q["hasta"]:
                return i
        if hoy > self.quincenas[-1]["hasta"]:
            return len(self.quincenas) - 1
        return 0

    def _mover(self, paso):
        nuevo = self._idx + paso
        if 0 <= nuevo < len(self.quincenas):
            self._idx = nuevo
            self._cargar()

    def _elegir_quincena(self, etiqueta):
        try:
            self._idx = self._etiquetas.index(etiqueta)
        except ValueError:
            return
        self._cargar()

    def _ir_a_hoy(self):
        self._idx = self._indice_hoy()
        self._cargar()
