# -*- coding: utf-8 -*-
"""
Kelly's Food - Raciones (planilla quincenal)
============================================
Reproduce la hoja de Excel de la clienta: filas = trabajadores, columnas =
días de la quincena, celdas = raciones de ese día. Se edita haciendo clic en
la celda y escribiendo el número (vacío = sin ración); se guarda solo.
No se muestra ningún ID: los trabajadores se manejan por nombre.
"""

from collections import Counter
from datetime import date, datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox

import customtkinter as ctk

import db
from ui import estilos

DIAS_SEMANA = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sa", "Do"]
IID_TOTAL = "__total__"
MAX_RACIONES_DIA = 99   # tope defensivo por celda (evita tecleos accidentales)
TOPE_DEUDAS = 6         # nº de quincenas con deuda que se listan en el panel


def _soles(v):
    return f"S/ {v:,.2f}"


class VistaRaciones(ctk.CTkFrame):
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
        self._dias = []
        self._datos = {}       # id_trabajador -> {fecha_iso: cantidad}
        self._fichas = {}      # id_trabajador -> (nombre_completo, telefono)
        self._estado_trab = {} # id_trabajador -> estado (Activo / Baja…)
        self._extra = {}       # id quincena -> {id: (nombre, telefono)} agregados a mano
        self._editor = None
        self._lista_sug = None
        self._sug_ids = []
        self._sel_panel = None   # id_trabajador mostrado en el panel lateral

        self.grid_columnconfigure(0, weight=3)
        # minsize evita que la columna del panel se colapse a 0 (y el panel se
        # desmapee) cuando la planilla se reconstruye al cambiar de quincena.
        self.grid_columnconfigure(1, weight=1, minsize=280)
        self.grid_rowconfigure(2, weight=1)
        self._construir_encabezado()
        self._construir_tabla()
        self._construir_panel()
        self._construir_pie()
        self._cargar()

    # ------------------------------------------------------------------
    # Encabezado: título + navegación de quincena + filtro por nombre
    # ------------------------------------------------------------------
    def _construir_encabezado(self):
        ctk.CTkLabel(self, text="Raciones", font=estilos.fuente(24, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=4, pady=(4, 8))

        barra = ctk.CTkFrame(self, corner_radius=12)
        barra.grid(row=1, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 10))
        fila = ctk.CTkFrame(barra, fg_color="transparent")
        fila.pack(fill="x", padx=12, pady=10)

        ctk.CTkButton(fila, text="◀", width=36, height=34,
                      command=lambda: self._mover(-1)).pack(side="left")
        self.combo_q = ctk.CTkComboBox(
            fila, values=self._etiquetas, width=300, height=34,
            command=self._elegir_quincena)
        self.combo_q.pack(side="left", padx=6)
        ctk.CTkButton(fila, text="▶", width=36, height=34,
                      command=lambda: self._mover(1)).pack(side="left")
        ctk.CTkButton(fila, text="Ir a hoy", width=80, height=34,
                      fg_color="transparent", border_width=1,
                      command=self._ir_a_hoy).pack(side="left", padx=(10, 0))
        ctk.CTkButton(fila, text="＋ Nueva quincena", width=140, height=34,
                      fg_color=estilos.AMBAR, hover_color=estilos.AMBAR_HOVER,
                      text_color="#20302A",
                      command=self._dialogo_nueva_quincena).pack(side="left", padx=(10, 0))

        self.e_filtro = ctk.CTkEntry(fila, width=220, height=34,
                                     placeholder_text="Buscar por nombre…")
        self.e_filtro.pack(side="right")
        self.e_filtro.bind("<KeyRelease>", lambda e: self._llenar())

    # ------------------------------------------------------------------
    # Tabla (planilla)
    # ------------------------------------------------------------------
    def _construir_tabla(self):
        cont = ctk.CTkFrame(self, corner_radius=12)
        cont.grid(row=2, column=0, sticky="nsew", padx=(4, 10))
        cont.grid_rowconfigure(0, weight=1)
        cont.grid_columnconfigure(0, weight=1)

        estilos.estilizar_treeview()
        self.tree = ttk.Treeview(cont, show="headings", style="Kelly.Treeview",
                                 selectmode="none")
        vsb = ttk.Scrollbar(cont, orient="vertical", command=self.tree.yview,
                            style="Kelly.Vertical.TScrollbar")
        hsb = ttk.Scrollbar(cont, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=(6, 0))
        vsb.grid(row=0, column=1, sticky="ns", pady=6, padx=(0, 6))
        hsb.grid(row=1, column=0, sticky="ew", padx=(6, 0))

        modo = ctk.get_appearance_mode()
        self.tree.tag_configure("par", background=estilos._lado(estilos.FONDO, modo))
        self.tree.tag_configure("baja", foreground=estilos._lado(
            estilos.TEXTO_TENUE, modo))
        self.tree.tag_configure("totales", background=estilos.VERDE_OSCURO,
                                foreground="#FFFFFF",
                                font=("Segoe UI Semibold", 11))
        self.tree.bind("<Button-1>", self._al_click)
        # Al hacer scroll se cierra el editor para que no quede flotando.
        self.tree.bind("<MouseWheel>", lambda e: self._cerrar_editor())

        self.lbl_resumen = ctk.CTkLabel(cont, text="", font=estilos.fuente(11),
                                        text_color=estilos.TEXTO_TENUE)
        self.lbl_resumen.grid(row=2, column=0, sticky="w", padx=10, pady=(2, 6))

    # ------------------------------------------------------------------
    # Pie: agregar trabajador por nombre + mensajes de estado
    # ------------------------------------------------------------------
    def _construir_pie(self):
        pie = ctk.CTkFrame(self, fg_color="transparent")
        pie.grid(row=3, column=0, columnspan=2, sticky="ew", padx=4, pady=(8, 2))

        ctk.CTkLabel(pie, text="＋ Agregar trabajador:",
                     font=estilos.fuente(12, "bold")).pack(side="left")
        self.e_nuevo = ctk.CTkEntry(pie, width=260, height=34,
                                    placeholder_text="Escribe el nombre…")
        self.e_nuevo.pack(side="left", padx=8)
        self.e_nuevo.bind("<KeyRelease>", self._sugerir)
        self.e_nuevo.bind("<Return>", lambda e: self._elegir_sugerencia(0))
        self.e_nuevo.bind("<Escape>", lambda e: self._ocultar_sugerencias())

        self.lbl_estado = ctk.CTkLabel(pie, text="", font=estilos.fuente(12),
                                       text_color=estilos.TEXTO_TENUE)
        self.lbl_estado.pack(side="left", padx=12)

    # ------------------------------------------------------------------
    # Panel lateral del trabajador (resumen + cobrar + precio + deudas)
    # ------------------------------------------------------------------
    def _construir_panel(self):
        # Igual que la de Trabajadores: CTkScrollableFrame con un árbol de widgets
        # FIJO que solo se actualiza (nunca se destruye/recrea). Así no hay
        # problemas de repintado al cambiar de trabajador o de quincena.
        panel = ctk.CTkScrollableFrame(self, corner_radius=12, label_text="Trabajador")
        panel.grid(row=2, column=1, sticky="nsew", padx=(0, 4))
        panel.grid_columnconfigure(0, weight=1)

        self.p_nombre = ctk.CTkLabel(
            panel, text="Haz clic en un trabajador\npara ver su resumen.",
            font=estilos.fuente(15, "bold"), wraplength=210, justify="left")
        self.p_nombre.grid(sticky="ew", padx=6, pady=(2, 0))
        self.p_tel = ctk.CTkLabel(panel, text="", font=estilos.fuente(11),
                                  text_color=estilos.TEXTO_TENUE)
        self.p_tel.grid(sticky="ew", padx=6, pady=(0, 6))

        self.p_resumen = ctk.CTkLabel(panel, text="", font=estilos.fuente(12),
                                      justify="left", wraplength=210)
        self.p_resumen.grid(sticky="ew", padx=6, pady=(0, 2))
        self.p_saldo = ctk.CTkLabel(panel, text="", font=estilos.fuente(15, "bold"))
        self.p_saldo.grid(sticky="ew", padx=6, pady=(0, 8))

        self.p_precio = ctk.CTkLabel(panel, text="", font=estilos.fuente(12, "bold"))
        self.p_precio.grid(sticky="ew", padx=6)
        self.p_btn_precio = ctk.CTkButton(
            panel, text="Cambiar precio", height=30, fg_color="transparent",
            border_width=1, command=self._panel_cambiar_precio)
        self.p_btn_precio.grid(sticky="ew", padx=6, pady=(2, 10))

        ctk.CTkLabel(panel, text="Registrar pago (esta quincena)", anchor="w",
                     font=estilos.fuente(12, "bold")).grid(sticky="ew", padx=6)
        self.p_monto = ctk.CTkEntry(panel, height=32, placeholder_text="Monto S/")
        self.p_monto.grid(sticky="ew", padx=6, pady=(2, 4))
        metodos = db.valores_columna("Metodo_Pago", "Metodo_Pago")
        self.p_metodo = ctk.CTkSegmentedButton(panel, values=metodos, height=30)
        if metodos:
            self.p_metodo.set(metodos[0])
        self.p_metodo.grid(sticky="ew", padx=6, pady=(0, 4))
        self.p_fecha = ctk.CTkEntry(panel, height=32)
        self.p_fecha.grid(sticky="ew", padx=6, pady=(0, 4))
        self.p_btn_pagar = ctk.CTkButton(panel, text="💾 Registrar pago", height=34,
                                         command=self._panel_registrar_pago)
        self.p_btn_pagar.grid(sticky="ew", padx=6, pady=(0, 4))
        self.p_msj = ctk.CTkLabel(panel, text="", font=estilos.fuente(11),
                                  wraplength=210, justify="left",
                                  text_color=estilos.TEXTO_TENUE)
        self.p_msj.grid(sticky="ew", padx=6, pady=(0, 6))

        # Deudas: árbol de widgets FIJO. Título + N filas (label + botón Pagar) +
        # "…y N más" + total. Se muestran/ocultan con grid()/grid_remove(), nunca
        # se destruyen. Cada fila puede saldar esa quincena desde aquí.
        self.p_deudas = ctk.CTkFrame(panel, fg_color="transparent")
        self.p_deudas.grid(sticky="ew", padx=2, pady=(0, 6))
        self.p_deudas.grid_columnconfigure(0, weight=1)

        self.p_deuda_titulo = ctk.CTkLabel(self.p_deudas, text="",
                                           font=estilos.fuente(11, "bold"))
        self.p_deuda_titulo.grid(row=0, column=0, sticky="w", padx=4, pady=(2, 2))

        self._deuda_slots = []
        for i in range(TOPE_DEUDAS):
            fila = ctk.CTkFrame(self.p_deudas, fg_color="transparent")
            fila.grid(row=1 + i, column=0, sticky="ew", padx=4, pady=1)
            fila.grid_columnconfigure(0, weight=1)
            lbl = ctk.CTkLabel(fila, text="", font=estilos.fuente(10),
                               wraplength=150, justify="left", anchor="w")
            lbl.grid(row=0, column=0, sticky="ew")
            btn = ctk.CTkButton(fila, text="Pagar", width=52, height=24,
                                font=estilos.fuente(11),
                                command=lambda i=i: self._pagar_deuda(i))
            btn.grid(row=0, column=1, padx=(4, 0))
            fila.grid_remove()
            self._deuda_slots.append({"fila": fila, "lbl": lbl, "deuda": None})

        self.p_deuda_mas = ctk.CTkLabel(self.p_deudas, text="",
                                        font=estilos.fuente(10),
                                        text_color=estilos.TEXTO_TENUE)
        self.p_deuda_mas.grid(row=1 + TOPE_DEUDAS, column=0, sticky="w", padx=8)
        self.p_deuda_total = ctk.CTkLabel(self.p_deudas, text="",
                                          font=estilos.fuente(11, "bold"))
        self.p_deuda_total.grid(row=2 + TOPE_DEUDAS, column=0, sticky="w",
                                padx=4, pady=(4, 0))

        self._panel_vacio()

    def _ventana(self):
        """(desde, hasta, fin): la ventana de pagos de la quincena actual llega
        hasta el inicio de la siguiente."""
        q = self.quincenas[self._idx]
        fin = (self.quincenas[self._idx + 1]["desde"]
               if self._idx + 1 < len(self.quincenas) else "9999-12-31")
        return q["desde"], q["hasta"], fin

    def _quincena_editable(self):
        """Una quincena solo se puede editar mientras su ventana no cerró (aún no
        empezó la siguiente). Las pasadas quedan de solo lectura; sus deudas se
        cobran desde el panel."""
        hoy = date.today().isoformat()
        if self._idx + 1 >= len(self.quincenas):
            return True
        return hoy < self.quincenas[self._idx + 1]["desde"]

    def _panel_widgets(self, estado):
        for w in (self.p_btn_precio, self.p_monto, self.p_metodo,
                  self.p_fecha, self.p_btn_pagar):
            w.configure(state=estado)

    def _panel_vacio(self):
        self._sel_panel = None
        self.p_nombre.configure(text="Haz clic en un trabajador\npara ver su resumen.")
        for w in (self.p_tel, self.p_resumen, self.p_saldo, self.p_precio,
                  self.p_msj, self.p_deuda_titulo, self.p_deuda_mas,
                  self.p_deuda_total):
            w.configure(text="")
        self.p_monto.delete(0, "end")
        self._panel_widgets("disabled")
        for slot in self._deuda_slots:
            slot["deuda"] = None
            slot["fila"].grid_remove()

    def _seleccionar_trabajador(self, tid):
        if not tid or tid == IID_TOTAL or tid not in self._fichas:
            return
        self._sel_panel = tid
        self._llenar_panel()

    def _llenar_panel(self):
        tid = self._sel_panel
        if not tid or tid not in self._fichas:
            self._panel_vacio()
            return
        desde, hasta, fin = self._ventana()
        r = db.cobranza_trabajador(tid, desde, hasta, fin)
        nombre, tel = self._fichas.get(tid, (tid, ""))
        es_baja = self._estado_trab.get(tid, db.ESTADO_ACTIVO) != db.ESTADO_ACTIVO
        self.p_nombre.configure(text=nombre + ("  (de baja)" if es_baja else ""))
        self.p_tel.configure(text=("📞 " + tel) if tel else "")

        d1 = datetime.strptime(desde, "%Y-%m-%d").strftime("%d/%m")
        d2 = datetime.strptime(hasta, "%Y-%m-%d").strftime("%d/%m")
        self.p_resumen.configure(
            text=f"Esta quincena ({d1}–{d2})\n"
                 f"Raciones:  {r['raciones']}\n"
                 f"A pagar:  {_soles(r['a_pagar'])}\n"
                 f"Pagó:  {_soles(r['pagado'])}")
        if r["saldo"] > 0.005:
            self.p_saldo.configure(text=f"Debe {_soles(r['saldo'])}",
                                   text_color=estilos.ROJO)
        elif r["saldo"] < -0.005:
            self.p_saldo.configure(text=f"A favor {_soles(-r['saldo'])}",
                                   text_color=estilos.AMBAR)
        else:
            self.p_saldo.configure(text="Al día", text_color=estilos.POSITIVO)

        self.p_precio.configure(text=f"Precio del menú: {_soles(r['precio'])}")
        self._panel_widgets("normal")
        self.p_monto.delete(0, "end")
        if r["saldo"] > 0.005:
            self.p_monto.insert(0, f"{r['saldo']:.2f}")
        hoy = date.today().isoformat()
        fecha = hoy if desde <= hoy < fin else max(desde, min(hoy, hasta))
        self.p_fecha.delete(0, "end")
        self.p_fecha.insert(0, datetime.strptime(fecha, "%Y-%m-%d").strftime("%d/%m/%Y"))
        self.p_msj.configure(text="")

        self._llenar_deudas(tid)

    def _llenar_deudas(self, tid):
        """Actualiza los slots FIJOS con las deudas de otras quincenas (nunca
        destruye/recrea widgets)."""
        deudas = db.deudas_pendientes(tid)
        actual = self.quincenas[self._idx]["id"]
        otras = [d for d in deudas if d["id"] != actual]
        total = sum(d["saldo"] for d in deudas)

        if not deudas:
            self.p_deuda_titulo.configure(text="✓ Sin deudas pendientes",
                                          text_color=estilos.POSITIVO)
        else:
            self.p_deuda_titulo.configure(
                text="⚠ También debe de:" if otras else "⚠ Deuda pendiente:",
                text_color=estilos.ROJO)

        for i, slot in enumerate(self._deuda_slots):
            if i < len(otras):
                d = otras[i]
                f1 = datetime.strptime(d["desde"], "%Y-%m-%d").strftime("%d/%m")
                f2 = datetime.strptime(d["hasta"], "%Y-%m-%d").strftime("%d/%m")
                slot["deuda"] = d
                slot["lbl"].configure(
                    text=f"{d['descripcion']}  {f1}–{f2}\n{_soles(d['saldo'])}")
                slot["fila"].grid()
            else:
                slot["deuda"] = None
                slot["fila"].grid_remove()

        resto = len(otras) - TOPE_DEUDAS
        self.p_deuda_mas.configure(
            text=f"…y {resto} quincena(s) más" if resto > 0 else "")
        self.p_deuda_total.configure(
            text=f"Deuda total: {_soles(total)}" if deudas else "")

    def _fin_ventana_de(self, qid):
        """Fin de la ventana de pagos de una quincena (inicio de la siguiente)."""
        for i, q in enumerate(self.quincenas):
            if q["id"] == qid:
                return (self.quincenas[i + 1]["desde"]
                        if i + 1 < len(self.quincenas) else "9999-12-31")
        return "9999-12-31"

    def _pagar_deuda(self, indice):
        tid = self._sel_panel
        slot = self._deuda_slots[indice]
        d = slot["deuda"]
        if not tid or not d:
            return
        self._dialogo_pagar_deuda(tid, d)

    def _dialogo_pagar_deuda(self, tid, d):
        fin = self._fin_ventana_de(d["id"])
        nombre = self._fichas.get(tid, (tid, ""))[0]
        metodos = db.valores_columna("Metodo_Pago", "Metodo_Pago")

        dlg = ctk.CTkToplevel(self)
        dlg.title("Pagar deuda")
        dlg.resizable(False, False)
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()
        v = self.winfo_toplevel()
        dlg.geometry(f"+{v.winfo_rootx() + 360}+{v.winfo_rooty() + 180}")
        m = ctk.CTkFrame(dlg, fg_color="transparent")
        m.pack(padx=22, pady=18)

        f1 = datetime.strptime(d["desde"], "%Y-%m-%d").strftime("%d/%m")
        f2 = datetime.strptime(d["hasta"], "%Y-%m-%d").strftime("%d/%m")
        ctk.CTkLabel(m, text=f"Cobrar a {nombre}", font=estilos.fuente(16, "bold")
                     ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(m, text=f"{d['descripcion']} ({f1}–{f2})  ·  debe "
                             f"{_soles(d['saldo'])}", font=estilos.fuente(12),
                     text_color=estilos.TEXTO_TENUE).grid(row=1, column=0,
                                                          sticky="w", pady=(0, 10))
        ctk.CTkLabel(m, text="Monto (S/)", anchor="w",
                     font=estilos.fuente(12, "bold")).grid(row=2, column=0, sticky="w")
        e_monto = ctk.CTkEntry(m, height=34, width=240)
        e_monto.insert(0, f"{d['saldo']:.2f}")
        e_monto.grid(row=3, column=0, sticky="ew", pady=(2, 8))
        seg = ctk.CTkSegmentedButton(m, values=metodos, height=32)
        if metodos:
            seg.set(metodos[0])
        seg.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        ctk.CTkLabel(m, text="Fecha (dd/mm/aaaa)", anchor="w",
                     font=estilos.fuente(12, "bold")).grid(row=5, column=0, sticky="w")
        e_fecha = ctk.CTkEntry(m, height=34)
        # Se fecha dentro de la quincena a saldar (último día) para que cuente.
        e_fecha.insert(0, datetime.strptime(d["hasta"], "%Y-%m-%d").strftime("%d/%m/%Y"))
        e_fecha.grid(row=6, column=0, sticky="ew", pady=(2, 8))
        lbl_err = ctk.CTkLabel(m, text="", font=estilos.fuente(11),
                               text_color=estilos.ROJO, wraplength=250, justify="left")
        lbl_err.grid(row=7, column=0, sticky="w")

        def confirmar():
            try:
                monto = round(float(e_monto.get().strip().replace(",", ".")), 2)
                if monto <= 0:
                    raise ValueError
            except ValueError:
                lbl_err.configure(text="⚠ Escribe el monto, por ejemplo 25.50.")
                return
            try:
                fecha = datetime.strptime(e_fecha.get().strip(),
                                          "%d/%m/%Y").date().isoformat()
            except ValueError:
                lbl_err.configure(text="⚠ La fecha debe ser dd/mm/aaaa.")
                return
            if not (d["desde"] <= fecha < fin):
                lbl_err.configure(text=f"⚠ Para saldar esta quincena, la fecha "
                                       f"debe estar entre {f1} y {f2}.")
                return
            metodo = seg.get()
            if not metodo:
                lbl_err.configure(text="⚠ Elige el método de pago.")
                return
            try:
                db.registrar_pago(tid, fecha, metodo, monto, d["desde"], fin)
            except Exception as ex:
                lbl_err.configure(text=f"⚠ No se pudo registrar: {ex}")
                return
            dlg.destroy()
            self._llenar_panel()
            self.p_msj.configure(text=f"Pago de {_soles(monto)} registrado para "
                                      f"{d['descripcion']}.",
                                 text_color=estilos.VERDE_HOVER)

        botones = ctk.CTkFrame(m, fg_color="transparent")
        botones.grid(row=8, column=0, sticky="ew", pady=(12, 0))
        ctk.CTkButton(botones, text="Registrar pago", height=34,
                      command=confirmar).pack(side="left")
        ctk.CTkButton(botones, text="Cancelar", height=34, width=90,
                      fg_color="transparent", border_width=1,
                      command=dlg.destroy).pack(side="left", padx=10)

    def _panel_cambiar_precio(self):
        tid = self._sel_panel
        if not tid:
            return
        actual = db.precio_trabajador_actual(tid)
        dlg = ctk.CTkToplevel(self)
        dlg.title("Precio del menú")
        dlg.resizable(False, False)
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()
        v = self.winfo_toplevel()
        dlg.geometry(f"+{v.winfo_rootx() + 360}+{v.winfo_rooty() + 200}")
        m = ctk.CTkFrame(dlg, fg_color="transparent")
        m.pack(padx=22, pady=18)
        nombre = self._fichas.get(tid, (tid, ""))[0]
        ctk.CTkLabel(m, text=f"Precio del menú de {nombre}",
                     font=estilos.fuente(16, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 4))
        ctk.CTkLabel(m, text="Rige desde la quincena actual; las anteriores no "
                             "cambian.",
                     font=estilos.fuente(11), text_color=estilos.TEXTO_TENUE,
                     wraplength=280, justify="left").grid(row=1, column=0, sticky="w",
                                                          pady=(0, 8))
        e = ctk.CTkEntry(m, height=34)
        e.insert(0, f"{actual:.2f}")
        e.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        lbl_err = ctk.CTkLabel(m, text="", font=estilos.fuente(11),
                               text_color=estilos.ROJO)
        lbl_err.grid(row=3, column=0, sticky="w")

        def confirmar():
            try:
                precio = round(float(e.get().strip().replace(",", ".")), 2)
                if precio <= 0:
                    raise ValueError
            except ValueError:
                lbl_err.configure(text="⚠ Escribe el precio, por ejemplo 8.00.")
                return
            db.fijar_precio_trabajador(tid, precio,
                                       desde=db.inicio_quincena_vigente())
            dlg.destroy()
            self._llenar_panel()
            self.p_msj.configure(text=f"Precio actualizado a {_soles(precio)} "
                                      "(desde esta quincena).",
                                 text_color=estilos.VERDE_HOVER)

        botones = ctk.CTkFrame(m, fg_color="transparent")
        botones.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        ctk.CTkButton(botones, text="Guardar", height=34,
                      command=confirmar).pack(side="left")
        ctk.CTkButton(botones, text="Cancelar", height=34, width=90,
                      fg_color="transparent", border_width=1,
                      command=dlg.destroy).pack(side="left", padx=10)

    def _panel_registrar_pago(self):
        tid = self._sel_panel
        if not tid:
            return
        try:
            monto = round(float(self.p_monto.get().strip().replace(",", ".")), 2)
        except ValueError:
            monto = -1
        if monto <= 0:
            self.p_msj.configure(text="⚠ Escribe el monto, por ejemplo 25.50.",
                                 text_color=estilos.ROJO)
            return
        try:
            fecha = datetime.strptime(self.p_fecha.get().strip(),
                                      "%d/%m/%Y").date().isoformat()
        except ValueError:
            self.p_msj.configure(text="⚠ La fecha debe ser dd/mm/aaaa.",
                                 text_color=estilos.ROJO)
            return
        desde, hasta, fin = self._ventana()
        if not (desde <= fecha < fin):
            self.p_msj.configure(
                text="⚠ La fecha del pago debe caer dentro de esta quincena.",
                text_color=estilos.ROJO)
            return
        metodo = self.p_metodo.get()
        if not metodo:
            self.p_msj.configure(text="⚠ Elige el método de pago.",
                                 text_color=estilos.ROJO)
            return
        r = db.cobranza_trabajador(tid, desde, hasta, fin)
        if monto > r["saldo"] + 0.005:
            exceso = monto - max(r["saldo"], 0)
            if not messagebox.askyesno(
                    "Confirmar pago",
                    f"El monto ({_soles(monto)}) supera lo que debe esta quincena "
                    f"({_soles(max(r['saldo'],0))}).\nQuedarán {_soles(exceso)} a "
                    "favor. ¿Registrar de todas formas?"):
                return
        nombre = self._fichas.get(tid, (tid, ""))[0]
        try:
            db.registrar_pago(tid, fecha, metodo, monto, desde, fin)
        except Exception as e:
            self.p_msj.configure(text=f"⚠ No se pudo registrar: {e}",
                                 text_color=estilos.ROJO)
            return
        self._llenar_panel()
        self.p_msj.configure(text=f"Pago de {_soles(monto)} registrado ({metodo}).",
                             text_color=estilos.VERDE_HOVER)

    # ------------------------------------------------------------------
    # Carga de datos de la quincena
    # ------------------------------------------------------------------
    def refrescar(self):
        """Recarga quincenas y datos desde la BD (se llama al mostrar la vista)."""
        if not getattr(self, "quincenas", None):
            return
        actual = self.quincenas[self._idx]["id"]
        self.quincenas = db.quincenas()
        self._etiquetas = [f"{q['desde'][:4]} · {q['descripcion']}"
                           for q in self.quincenas]
        self.combo_q.configure(values=self._etiquetas)
        self._idx = next((i for i, q in enumerate(self.quincenas)
                          if q["id"] == actual), self._indice_hoy())
        self._cargar()

    def _cargar(self):
        self._cerrar_editor()
        self._ocultar_sugerencias()
        q = self.quincenas[self._idx]
        self.combo_q.set(self._etiquetas[self._idx])
        self._dias = self._rango_dias(q["desde"], q["hasta"])

        self._datos = {}
        self._estado_trab = {}
        for f in db.raciones_quincena(q["desde"], q["hasta"]):
            tid = f["id_trabajador"]
            self._datos.setdefault(tid, {})[f["Fecha"]] = f["Cantidad_Raciones"]
            self._fichas[tid] = (f"{f['Nombre']} {f['Apellido']}", f["Telefono"])
            self._estado_trab[tid] = f["Estado"]
        # Trabajadores agregados a mano (todavía sin raciones en la quincena).
        # Solo se agregan Activos (buscar_trabajadores ya filtra), por eso Activo.
        for tid, ficha in self._extra.get(q["id"], {}).items():
            self._datos.setdefault(tid, {})
            self._fichas.setdefault(tid, ficha)
            self._estado_trab.setdefault(tid, db.ESTADO_ACTIVO)

        self._reconstruir_columnas()
        self._llenar()
        # En quincenas cerradas no se agregan trabajadores (no se les puede
        # anotar raciones); se deshabilita el cuadro para evitar callejones.
        editable = self._quincena_editable()
        self.e_nuevo.configure(state="normal" if editable else "disabled")
        # Refrescar el panel (el saldo depende de la quincena mostrada).
        if self._sel_panel:
            self._llenar_panel()

    def _reconstruir_columnas(self):
        cols = ["nombre"] + self._dias + ["total"]
        self.tree["columns"] = cols
        self.tree.heading("nombre", text="Trabajador", anchor="w")
        self.tree.column("nombre", width=185, minwidth=150, anchor="w", stretch=False)
        for iso in self._dias:
            f = datetime.strptime(iso, "%Y-%m-%d")
            self.tree.heading(iso, text=f"{DIAS_SEMANA[f.weekday()]} {f.strftime('%d/%m')}")
            self.tree.column(iso, width=86, minwidth=70, anchor="center", stretch=False)
        self.tree.heading("total", text="Total")
        self.tree.column("total", width=70, minwidth=60, anchor="center", stretch=False)

    def _nombre_visible(self, tid, repetidos):
        nombre, telefono = self._fichas.get(tid, (tid, ""))
        if repetidos[nombre] > 1 and telefono:
            return f"{nombre} ({telefono})"
        return nombre

    def _llenar(self):
        self._cerrar_editor()
        self.tree.delete(*self.tree.get_children())
        filtro = self.e_filtro.get().strip().lower()

        ids = sorted(self._datos)  # mismo orden que su Excel (por código interno)
        repetidos = Counter(self._fichas.get(t, (t, ""))[0] for t in ids)
        visibles = 0
        for tid in ids:
            nombre = self._nombre_visible(tid, repetidos)
            if filtro and filtro not in nombre.lower():
                continue
            es_baja = self._estado_trab.get(tid, db.ESTADO_ACTIVO) != db.ESTADO_ACTIVO
            etiqueta = nombre + ("  (de baja)" if es_baja else "")
            d = self._datos[tid]
            fila = [etiqueta] + [d.get(dia) or 0 for dia in self._dias] + [0]
            tags = []
            if visibles % 2:
                tags.append("par")
            if es_baja:
                tags.append("baja")
            self.tree.insert("", "end", iid=tid, values=fila, tags=tuple(tags))
            visibles += 1
        self.tree.insert("", "end", iid=IID_TOTAL,
                         values=["TOTAL DEL DÍA"] + [0] * (len(self._dias) + 1),
                         tags=("totales",))
        self._refrescar_totales()

    def _refrescar_totales(self):
        visibles = [i for i in self.tree.get_children() if i != IID_TOTAL]
        tot_dia = {d: 0 for d in self._dias}
        total_q = 0
        for tid in visibles:
            datos = self._datos.get(tid, {})
            tot = 0
            for d in self._dias:
                c = datos.get(d)
                if c:
                    tot += c
                    tot_dia[d] += c
            self.tree.set(tid, "total", tot)
            total_q += tot
        if self.tree.exists(IID_TOTAL):
            for d in self._dias:
                self.tree.set(IID_TOTAL, d, tot_dia[d])
            self.tree.set(IID_TOTAL, "total", total_q)
        nota = "" if self._quincena_editable() else "   ·   🔒 Cerrada (solo lectura)"
        self.lbl_resumen.configure(
            text=f"{len(visibles)} trabajador(es) · {total_q:,} "
                 f"raciones en la quincena{nota}")

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

    @staticmethod
    def _rango_dias(desde, hasta):
        # Sin domingos: no se reparte almuerzo ese día.
        d = date.fromisoformat(desde)
        h = date.fromisoformat(hasta)
        out = []
        while d <= h:
            if d.weekday() != 6:
                out.append(d.isoformat())
            d += timedelta(days=1)
        return out

    # ------------------------------------------------------------------
    # Nueva quincena
    # ------------------------------------------------------------------
    def _dialogo_nueva_quincena(self):
        self._cerrar_editor()
        desde, hasta = db.sugerir_quincena()

        dlg = ctk.CTkToplevel(self)
        dlg.title("Nueva quincena")
        dlg.resizable(False, False)
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()
        ventana = self.winfo_toplevel()
        dlg.geometry(f"+{ventana.winfo_rootx() + 340}+{ventana.winfo_rooty() + 180}")

        marco = ctk.CTkFrame(dlg, fg_color="transparent")
        marco.pack(padx=22, pady=18)
        ctk.CTkLabel(marco, text="Crear la siguiente quincena",
                     font=estilos.fuente(17, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        ctk.CTkLabel(marco, font=estilos.fuente(12),
                     text_color=estilos.TEXTO_TENUE, justify="left",
                     text="Las fechas ya vienen sugeridas (empieza donde\n"
                          "terminó la última). Cámbialas si hace falta.").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(0, 10))

        ctk.CTkLabel(marco, text="Primer día (dd/mm/aaaa)",
                     font=estilos.fuente(12, "bold")).grid(row=2, column=0,
                                                           sticky="w", padx=(0, 12))
        ctk.CTkLabel(marco, text="Último día (dd/mm/aaaa)",
                     font=estilos.fuente(12, "bold")).grid(row=2, column=1, sticky="w")
        e_desde = ctk.CTkEntry(marco, width=150, height=34)
        e_desde.insert(0, self._a_ddmma(desde))
        e_desde.grid(row=3, column=0, sticky="w", padx=(0, 12), pady=(2, 10))
        e_hasta = ctk.CTkEntry(marco, width=150, height=34)
        e_hasta.insert(0, self._a_ddmma(hasta))
        e_hasta.grid(row=3, column=1, sticky="w", pady=(2, 10))

        copiar = ctk.CTkCheckBox(
            marco, text="Empezar con los trabajadores de la quincena anterior",
            font=estilos.fuente(12))
        copiar.select()
        copiar.grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 10))

        lbl_error = ctk.CTkLabel(marco, text="", font=estilos.fuente(11),
                                 text_color=estilos.ROJO, wraplength=330,
                                 justify="left")
        lbl_error.grid(row=5, column=0, columnspan=2, sticky="w")

        def confirmar():
            try:
                d1 = self._de_ddmma(e_desde.get())
                d2 = self._de_ddmma(e_hasta.get())
            except ValueError:
                lbl_error.configure(text="⚠ Escribe las fechas como dd/mm/aaaa, "
                                         "por ejemplo 15/06/2026.")
                return
            try:
                self._crear_quincena(d1, d2, bool(copiar.get()))
            except ValueError as ex:
                lbl_error.configure(text=f"⚠ {ex}")
                return
            dlg.destroy()

        botones = ctk.CTkFrame(marco, fg_color="transparent")
        botones.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ctk.CTkButton(botones, text="Crear quincena", height=36,
                      command=confirmar).pack(side="left")
        ctk.CTkButton(botones, text="Cancelar", height=36, width=100,
                      fg_color="transparent", border_width=1,
                      command=dlg.destroy).pack(side="left", padx=10)

    def _crear_quincena(self, desde, hasta, copiar_trabajadores):
        """Crea el período, opcionalmente arrastra los trabajadores de la
        quincena anterior y muestra la planilla nueva."""
        anterior = self.quincenas[-1] if self.quincenas else None
        nueva = db.crear_quincena(desde, hasta)

        self.quincenas = db.quincenas()
        self._etiquetas = [f"{q['desde'][:4]} · {q['descripcion']}"
                           for q in self.quincenas]
        self.combo_q.configure(values=self._etiquetas)
        self._idx = next(i for i, q in enumerate(self.quincenas)
                         if q["id"] == nueva["id"])

        if copiar_trabajadores and anterior:
            fichas = {}
            for f in db.raciones_quincena(anterior["desde"], anterior["hasta"]):
                # No arrastrar a los que están de baja: ya no reciben almuerzos.
                if f["Estado"] != db.ESTADO_ACTIVO:
                    continue
                fichas[f["id_trabajador"]] = (f"{f['Nombre']} {f['Apellido']}",
                                              f["Telefono"])
            self._extra[nueva["id"]] = fichas

        self._cargar()
        self._estado(f"{nueva['descripcion']} creada; ya puedes registrar raciones.")

    @staticmethod
    def _a_ddmma(iso):
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d/%m/%Y")

    @staticmethod
    def _de_ddmma(texto):
        texto = texto.strip()
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(texto, fmt).date().isoformat()
            except ValueError:
                continue
        raise ValueError(texto)

    # ------------------------------------------------------------------
    # Edición de celdas (clic → escribir → Enter)
    # ------------------------------------------------------------------
    def _al_click(self, event):
        self._cerrar_editor()
        self._ocultar_sugerencias()
        if self.tree.identify("region", event.x, event.y) != "cell":
            return
        rowid = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if rowid and rowid != IID_TOTAL:
            self._seleccionar_trabajador(rowid)  # llena el panel lateral
        self._abrir_editor(rowid, col)

    def _abrir_editor(self, rowid, col):
        if not rowid or rowid == IID_TOTAL:
            return
        ci = int(col[1:]) - 1          # 0 = nombre, 1..n = días, n+1 = total
        if ci < 1 or ci > len(self._dias):
            return   # clic en nombre/total: no hay celda editable (solo selección)
        if not self._quincena_editable():
            self._estado("Esta quincena ya cerró; no se pueden cambiar las "
                         "raciones (pero sí puedes cobrar sus deudas en el panel).",
                         error=True)
            return
        if self._estado_trab.get(rowid, db.ESTADO_ACTIVO) != db.ESTADO_ACTIVO:
            self._estado("Este trabajador está de baja; no se le pueden anotar "
                         "raciones. Reactívalo en «Trabajadores» si vuelve.",
                         error=True)
            return
        bbox = self.tree.bbox(rowid, col)
        if not bbox:
            return
        x, y, ancho, alto = bbox
        e = tk.Entry(self.tree, justify="center", font=("Segoe UI", 11),
                     relief="solid", bd=1)
        e.insert(0, self.tree.set(rowid, col))
        e.select_range(0, "end")
        e.place(x=x, y=y, width=ancho, height=alto)
        e.focus_set()
        e.bind("<Return>", lambda ev: self._confirmar(siguiente="abajo"))
        e.bind("<Tab>", lambda ev: self._confirmar(siguiente="derecha") or "break")
        e.bind("<Escape>", lambda ev: self._cerrar_editor())
        e.bind("<FocusOut>", lambda ev: self._confirmar())
        self._editor = (e, rowid, col)

    def _cerrar_editor(self):
        if self._editor:
            e, _, _ = self._editor
            self._editor = None
            e.destroy()

    def _confirmar(self, siguiente=None):
        if not self._editor:
            return
        e, rowid, col = self._editor
        texto = e.get().strip()
        self._cerrar_editor()

        if texto and not texto.isdigit():
            self._estado("⚠ Escribe solo el número de raciones (o deja vacío).",
                         error=True)
            return
        cantidad = int(texto) if texto else 0
        if cantidad > MAX_RACIONES_DIA:
            self._estado(f"⚠ ¿{cantidad} raciones en un día? El máximo es "
                         f"{MAX_RACIONES_DIA}. Corrige el número.", error=True)
            return
        fecha = self._dias[int(col[1:]) - 2]
        anterior = self._datos.get(rowid, {}).get(fecha) or 0
        if cantidad != anterior:
            try:
                db.fijar_racion(rowid, fecha, cantidad)
            except Exception as ex:
                self._estado(f"⚠ No se pudo guardar: {ex}", error=True)
                return
            if cantidad:
                self._datos.setdefault(rowid, {})[fecha] = cantidad
            else:
                self._datos.setdefault(rowid, {}).pop(fecha, None)
            self.tree.set(rowid, col, cantidad or 0)
            self._refrescar_totales()
            f = datetime.strptime(fecha, "%Y-%m-%d").strftime("%d/%m")
            nombre = self.tree.set(rowid, "nombre")
            self._estado(f"Guardado: {nombre}, {f} = {cantidad or 0}.")

        # Navegación estilo Excel.
        if siguiente == "abajo":
            filas = [i for i in self.tree.get_children() if i != IID_TOTAL]
            try:
                pos = filas.index(rowid)
            except ValueError:
                return
            if pos + 1 < len(filas):
                self.tree.see(filas[pos + 1])
                self._abrir_editor(filas[pos + 1], col)
        elif siguiente == "derecha":
            ci = int(col[1:])
            if ci <= len(self._dias):
                self._abrir_editor(rowid, f"#{ci + 1}")

    def _estado(self, texto, error=False):
        self.lbl_estado.configure(
            text=texto,
            text_color=estilos.ROJO if error else estilos.TEXTO_TENUE)

    # ------------------------------------------------------------------
    # Autocompletado para agregar trabajadores por nombre
    # ------------------------------------------------------------------
    def _sugerir(self, event=None):
        if event and event.keysym in ("Return", "Escape", "Up", "Down"):
            return
        texto = self.e_nuevo.get().strip()
        if len(texto) < 2:
            self._ocultar_sugerencias()
            return
        filas = db.buscar_trabajadores(texto)
        if not filas:
            self._ocultar_sugerencias()
            self._estado("No se encontró; puedes crearlo en «Trabajadores».")
            return
        self._estado("")
        self._sug_ids = [(f["id_trabajador"],
                          f"{f['Nombre']} {f['Apellido']}", f["Telefono"])
                         for f in filas]
        if self._lista_sug is None:
            self._lista_sug = tk.Listbox(
                self, font=("Segoe UI", 11), activestyle="none",
                relief="solid", bd=1, highlightthickness=0)
            self._lista_sug.bind(
                "<ButtonRelease-1>",
                lambda e: self._elegir_sugerencia(self._lista_sug.nearest(e.y)))
        lb = self._lista_sug
        lb.delete(0, "end")
        for _tid, nombre, tel in self._sug_ids:
            lb.insert("end", f"  {nombre} — {tel}")
        alto = min(len(self._sug_ids), 6)
        lb.configure(height=alto)
        # Desplegar hacia arriba, pegada al cuadro de texto.
        x = self.e_nuevo.winfo_rootx() - self.winfo_rootx()
        y = self.e_nuevo.winfo_rooty() - self.winfo_rooty()
        lb.place(x=x, y=y - alto * 22 - 6, width=320)
        lb.lift()

    def _ocultar_sugerencias(self):
        if self._lista_sug is not None:
            self._lista_sug.place_forget()

    def _elegir_sugerencia(self, indice):
        if not self._sug_ids or self._lista_sug is None \
                or not self._lista_sug.winfo_ismapped():
            return
        if not (0 <= indice < len(self._sug_ids)):
            indice = 0
        tid, nombre, tel = self._sug_ids[indice]
        self._ocultar_sugerencias()
        self.e_nuevo.delete(0, "end")

        if tid in self._datos:
            self.e_filtro.delete(0, "end")
            self.e_filtro.insert(0, nombre)
            self._llenar()
            self._estado(f"{nombre} ya está en la planilla; te lo muestro.")
            return
        self._extra.setdefault(self.quincenas[self._idx]["id"], {})[tid] = (nombre, tel)
        self._datos[tid] = {}
        self._fichas[tid] = (nombre, tel)
        self.e_filtro.delete(0, "end")
        self._llenar()
        if self.tree.exists(tid):
            self.tree.see(tid)
        self._estado(f"{nombre} agregado: haz clic en un día para poner sus raciones.")
