# -*- coding: utf-8 -*-
"""
Kelly's Food - Compras (insumos)
================================
Pensada para la clienta: registra lo que compra por NOMBRE del insumo y del
proveedor, con la cantidad y lo que pagó. Nada de códigos ni IDs: el número de
compra se genera solo por dentro. Fechas en dd/mm/aaaa.

  * Tabla a la izquierda: las compras más recientes primero.
  * Formulario a la derecha: fecha, proveedor, insumo, cantidad y costo.
  * Selecciona una fila para editarla o borrarla; «Nuevo» limpia para registrar.
"""

from datetime import date, datetime
from tkinter import ttk, messagebox

import customtkinter as ctk

import db
from ui import estilos


def _soles(v):
    return f"S/ {v:,.2f}"


class VistaCompras(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self._sel = None                 # id_compra seleccionado (interno, oculto)
        self._filas = {}                 # id -> fila
        self._insumos = db.insumos_conocidos()       # [(nombre, unidad)]
        self._unidad_de = {n: u for n, u in self._insumos}
        self._proveedores = db.proveedores_conocidos()  # [(ruc, nombre)]
        self._ruc_de = {n: r for r, n in self._proveedores}

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._construir_barra()
        self._construir_tabla()
        self._construir_formulario()
        self.refrescar()

    # ------------------------------------------------------------------
    def _construir_barra(self):
        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.grid(row=0, column=0, columnspan=2, sticky="ew", padx=4, pady=(4, 8))
        barra.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(barra, text="Compras",
                     font=estilos.fuente(22, "bold")).grid(row=0, column=0, sticky="w")

        self.e_busqueda = ctk.CTkEntry(
            barra, placeholder_text="Buscar por insumo, proveedor o fecha…",
            width=300, height=36)
        self.e_busqueda.grid(row=0, column=1, sticky="e", padx=(0, 8))
        self.e_busqueda.bind("<Return>", lambda e: self.refrescar())
        ctk.CTkButton(barra, text="Buscar", width=90, height=36,
                      command=self.refrescar).grid(row=0, column=2, padx=4)
        ctk.CTkButton(barra, text="Limpiar", width=90, height=36,
                      fg_color="transparent", border_width=1,
                      command=self._limpiar_busqueda).grid(row=0, column=3)

    # ------------------------------------------------------------------
    def _construir_tabla(self):
        cont = ctk.CTkFrame(self, corner_radius=12)
        cont.grid(row=1, column=0, sticky="nsew", padx=(4, 10))
        cont.grid_rowconfigure(0, weight=1)
        cont.grid_columnconfigure(0, weight=1)

        estilos.estilizar_treeview()
        cols = ("fecha", "proveedor", "insumo", "cantidad", "costo")
        self.tree = ttk.Treeview(cont, columns=cols, show="headings",
                                 style="Kelly.Treeview", selectmode="browse")
        for col, etiqueta, ancho, ancla in (
                ("fecha", "Fecha", 100, "center"),
                ("proveedor", "Proveedor", 200, "w"),
                ("insumo", "Insumo", 150, "w"),
                ("cantidad", "Cantidad", 110, "center"),
                ("costo", "Costo", 100, "e")):
            self.tree.heading(col, text=etiqueta)
            self.tree.column(col, width=ancho, anchor=ancla)

        vsb = ttk.Scrollbar(cont, orient="vertical", command=self.tree.yview,
                            style="Kelly.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=6)
        vsb.grid(row=0, column=1, sticky="ns", pady=6, padx=(0, 6))

        modo = ctk.get_appearance_mode()
        self.tree.tag_configure("par", background=estilos._lado(estilos.FONDO, modo))
        self.tree.bind("<<TreeviewSelect>>", self._al_seleccionar)

        self.lbl_conteo = ctk.CTkLabel(cont, text="", font=estilos.fuente(11),
                                       text_color=estilos.TEXTO_TENUE)
        self.lbl_conteo.grid(row=1, column=0, columnspan=2, sticky="w",
                             padx=10, pady=(0, 6))

    # ------------------------------------------------------------------
    def _construir_formulario(self):
        panel = ctk.CTkScrollableFrame(self, corner_radius=12,
                                       label_text="Registrar compra")
        panel.grid(row=1, column=1, sticky="nsew", padx=(0, 4))
        panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(panel, text="Fecha (dd/mm/aaaa)", anchor="w",
                     font=estilos.fuente(12, "bold")).grid(sticky="ew", padx=6, pady=(8, 0))
        self.e_fecha = ctk.CTkEntry(panel, height=34)
        self.e_fecha.grid(sticky="ew", padx=6, pady=(2, 6))

        ctk.CTkLabel(panel, text="Proveedor", anchor="w",
                     font=estilos.fuente(12, "bold")).grid(sticky="ew", padx=6)
        self.combo_prov = ctk.CTkComboBox(
            panel, values=[n for _r, n in self._proveedores], height=34)
        self.combo_prov.set(self._proveedores[0][1] if self._proveedores else "")
        self.combo_prov.grid(sticky="ew", padx=6, pady=(2, 6))

        ctk.CTkLabel(panel, text="Insumo", anchor="w",
                     font=estilos.fuente(12, "bold")).grid(sticky="ew", padx=6)
        self.combo_insumo = ctk.CTkComboBox(
            panel, values=[n for n, _u in self._insumos], height=34,
            command=self._al_cambiar_insumo)
        self.combo_insumo.set("")
        self.combo_insumo.grid(sticky="ew", padx=6, pady=(2, 6))

        ctk.CTkLabel(panel, text="Cantidad", anchor="w",
                     font=estilos.fuente(12, "bold")).grid(sticky="ew", padx=6)
        fila_cant = ctk.CTkFrame(panel, fg_color="transparent")
        fila_cant.grid(sticky="ew", padx=6, pady=(2, 6))
        fila_cant.grid_columnconfigure(0, weight=1)
        self.e_cantidad = ctk.CTkEntry(fila_cant, height=34,
                                       placeholder_text="Ej: 20")
        self.e_cantidad.grid(row=0, column=0, sticky="ew")
        self.lbl_unidad = ctk.CTkLabel(fila_cant, text="", width=90,
                                       font=estilos.fuente(12),
                                       text_color=estilos.TEXTO_TENUE)
        self.lbl_unidad.grid(row=0, column=1, sticky="w", padx=(8, 0))

        ctk.CTkLabel(panel, text="Costo total (S/)", anchor="w",
                     font=estilos.fuente(12, "bold")).grid(sticky="ew", padx=6)
        self.e_costo = ctk.CTkEntry(panel, height=34, placeholder_text="Ej: 85.50")
        self.e_costo.grid(sticky="ew", padx=6, pady=(2, 10))

        botones = ctk.CTkFrame(panel, fg_color="transparent")
        botones.grid(sticky="ew", pady=6)
        botones.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(botones, text="＋ Nueva", command=self.nuevo,
                      fg_color=estilos.AMBAR, hover_color=estilos.AMBAR_HOVER,
                      text_color="#20302A").grid(row=0, column=0, sticky="ew", pady=3)
        ctk.CTkButton(botones, text="💾 Guardar", command=self.guardar).grid(
            row=1, column=0, sticky="ew", pady=3)
        self.btn_eliminar = ctk.CTkButton(botones, text="🗑 Eliminar",
                                          command=self.eliminar,
                                          fg_color=estilos.ROJO,
                                          hover_color=estilos.ROJO_HOVER)
        self.btn_eliminar.grid(row=2, column=0, sticky="ew", pady=3)

        self.lbl_msj = ctk.CTkLabel(panel, text="Registra una compra: elige el "
                                              "insumo, la cantidad y lo que pagaste.",
                                    font=estilos.fuente(11), wraplength=220,
                                    justify="left", text_color=estilos.TEXTO_TENUE)
        self.lbl_msj.grid(sticky="ew", padx=6, pady=(4, 8))
        self.nuevo()

    def _al_cambiar_insumo(self, _v=None):
        nombre = self.combo_insumo.get().strip()
        if nombre in self._unidad_de:
            self.lbl_unidad.configure(text=self._unidad_de[nombre].lower())
        elif nombre:
            self.lbl_unidad.configure(text="nuevo (en kg)")
        else:
            self.lbl_unidad.configure(text="")

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------
    def refrescar(self):
        filas = db.compras_recientes(self.e_busqueda.get())
        self._filas = {f["id"]: dict(f) for f in filas}
        self.tree.delete(*self.tree.get_children())
        total = 0.0
        for i, f in enumerate(filas):
            total += f["costo"] or 0
            self.tree.insert("", "end", iid=f["id"], values=(
                self._ddmma(f["fecha"]), f["proveedor"], f["insumo"],
                f"{self._num(f['cantidad'])} {f['unidad'].lower()}".strip(),
                _soles(f["costo"] or 0)),
                tags=("par",) if i % 2 else ())
        self.lbl_conteo.configure(
            text=f"{len(filas)} compra(s) · total mostrado {_soles(total)}")
        if self._sel and not self.tree.exists(self._sel):
            self._sel = None
        self._reflejar_botones()

    def _al_seleccionar(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        self._sel = sel[0]
        f = self._filas.get(self._sel, {})
        self.e_fecha.delete(0, "end")
        self.e_fecha.insert(0, self._ddmma(f.get("fecha", "")))
        if f.get("proveedor"):
            self.combo_prov.set(f["proveedor"])
        self.combo_insumo.set(f.get("insumo", ""))
        self._al_cambiar_insumo()
        self.e_cantidad.delete(0, "end")
        self.e_cantidad.insert(0, self._num(f.get("cantidad", 0)))
        self.e_costo.delete(0, "end")
        self.e_costo.insert(0, f"{f.get('costo', 0):.2f}")
        self._reflejar_botones()
        self._msj("Editando esta compra; cambia lo que quieras y pulsa Guardar.")

    def _reflejar_botones(self):
        self.btn_eliminar.configure(
            state="normal" if self._sel else "disabled")

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def nuevo(self):
        self._sel = None
        self.tree.selection_remove(self.tree.selection())
        self.e_fecha.delete(0, "end")
        self.e_fecha.insert(0, date.today().strftime("%d/%m/%Y"))
        self.combo_insumo.set("")
        self._al_cambiar_insumo()
        self.e_cantidad.delete(0, "end")
        self.e_costo.delete(0, "end")
        self._reflejar_botones()
        self._msj("Nueva compra: completa los datos y pulsa Guardar.",
                  color=estilos.VERDE_HOVER)

    def _validar(self):
        try:
            fecha = datetime.strptime(self.e_fecha.get().strip(),
                                      "%d/%m/%Y").date().isoformat()
        except ValueError:
            return None, ("La fecha debe ser dd/mm/aaaa, por ejemplo "
                          f"{date.today().strftime('%d/%m/%Y')}.")
        insumo = self.combo_insumo.get().strip()
        if not insumo:
            return None, "Elige o escribe el insumo que compraste."
        try:
            cantidad = float(self.e_cantidad.get().strip().replace(",", "."))
            if cantidad <= 0:
                raise ValueError
        except ValueError:
            return None, "Escribe la cantidad (un número mayor que 0)."
        try:
            costo = round(float(self.e_costo.get().strip().replace(",", ".")), 2)
            if costo <= 0:
                raise ValueError
        except ValueError:
            return None, "Escribe el costo en soles, por ejemplo 85.50."
        prov_txt = self.combo_prov.get().strip()
        if prov_txt and prov_txt not in self._ruc_de:
            return None, ("Ese proveedor no está en la lista. Elige uno de la lista "
                          "(o créalo primero).")
        ruc = self._ruc_de.get(prov_txt)
        return {"fecha": fecha, "insumo": insumo, "cantidad": cantidad,
                "costo": costo, "ruc": ruc}, None

    def guardar(self):
        datos, error = self._validar()
        if error:
            self._msj("⚠ " + error, color=estilos.ROJO)
            return
        try:
            if self._sel:
                db.editar_compra(self._sel, datos["fecha"], datos["insumo"],
                                 datos["cantidad"], datos["costo"], datos["ruc"])
                msj = "Compra actualizada."
            else:
                self._sel = db.registrar_compra(
                    datos["fecha"], datos["insumo"], datos["cantidad"],
                    datos["costo"], datos["ruc"])
                msj = f"Compra registrada: {datos['insumo']} por {_soles(datos['costo'])}."
        except Exception as e:
            self._msj(f"⚠ No se pudo guardar: {e}", color=estilos.ROJO)
            return
        self.refrescar()
        if self.tree.exists(self._sel):
            self.tree.selection_set(self._sel)
            self.tree.see(self._sel)
        self._msj(msj, color=estilos.VERDE_HOVER)

    def eliminar(self):
        if not self._sel:
            return
        f = self._filas.get(self._sel, {})
        detalle = f"{f.get('insumo', '')} del {self._ddmma(f.get('fecha', ''))}"
        if not messagebox.askyesno("Eliminar compra",
                                   f"¿Eliminar la compra de {detalle}?"):
            return
        try:
            db.eliminar_compra(self._sel)
        except Exception as e:
            self._msj(f"⚠ No se pudo eliminar: {e}", color=estilos.ROJO)
            return
        self._sel = None
        self.refrescar()
        self.nuevo()
        self._msj("Compra eliminada.", color=estilos.AMBAR)

    # ------------------------------------------------------------------
    def _limpiar_busqueda(self):
        self.e_busqueda.delete(0, "end")
        self.refrescar()

    @staticmethod
    def _ddmma(iso):
        if not iso:
            return ""
        try:
            return datetime.strptime(iso, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            return iso

    @staticmethod
    def _num(v):
        """Muestra la cantidad sin decimales innecesarios (20 en vez de 20.0)."""
        try:
            v = float(v)
        except (TypeError, ValueError):
            return str(v)
        return str(int(v)) if v == int(v) else f"{v:g}"

    def _msj(self, texto, color=None):
        self.lbl_msj.configure(text=texto,
                               text_color=color or estilos.TEXTO_TENUE)
