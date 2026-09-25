# -*- coding: utf-8 -*-
"""
Kelly's Food - Trabajadores
===========================
Alta y baja de trabajadores pensada para la clienta:
  * El código interno (001ALCO) se genera solo; nunca se pide ni se muestra.
  * No se elimina a nadie: se da de baja y así se conserva el historial.
  * Dos tipos de baja:
      - Temporal (DT): se fue por un tiempo, puede reincorporarse.
      - Definitiva: retirado de la empresa; no se puede reactivar.
    En ambos casos deja de aparecer para anotarle raciones.
  * Al dar de baja se guarda el motivo y la fecha, y se avisa si tiene deuda.
  * Al dar de alta se avisa si el teléfono ya lo usa otro trabajador.
"""

from datetime import date, datetime
from tkinter import ttk, messagebox

import customtkinter as ctk

import db
from ui import estilos

# Etiquetas visibles del filtro -> estado real en la BD (None = todos).
FILTROS = {
    "Todos": None,
    "Activos": db.ESTADO_ACTIVO,
    "Baja temporal": db.ESTADO_TEMPORAL,
    "Baja definitiva": db.ESTADO_DEFINITIVA,
}


def _soles(v):
    return f"S/ {v:,.2f}"


class VistaTrabajadores(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self._sel = None            # id_trabajador seleccionado (interno)
        self._filas = {}            # id -> fila completa (incluye motivo/fecha)
        self._dup_confirmado = False
        self._precio_cargado = None  # precio del menú del trabajador seleccionado

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._construir_barra()
        self._construir_filtro()
        self._construir_tabla()
        self._construir_formulario()
        self.refrescar()

    # ------------------------------------------------------------------
    def _construir_barra(self):
        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.grid(row=0, column=0, columnspan=2, sticky="ew", padx=4, pady=(4, 8))
        barra.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(barra, text="Trabajadores",
                     font=estilos.fuente(22, "bold")).grid(row=0, column=0, sticky="w")

        self.e_busqueda = ctk.CTkEntry(barra, placeholder_text="Buscar por nombre o teléfono…",
                                       width=280, height=36)
        self.e_busqueda.grid(row=0, column=1, sticky="e", padx=(0, 8))
        self.e_busqueda.bind("<Return>", lambda e: self.refrescar())
        ctk.CTkButton(barra, text="Buscar", width=90, height=36,
                      command=self.refrescar).grid(row=0, column=2, padx=4)
        ctk.CTkButton(barra, text="Limpiar", width=90, height=36,
                      fg_color="transparent", border_width=1,
                      command=self._limpiar_busqueda).grid(row=0, column=3)

    def _construir_filtro(self):
        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.grid(row=1, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 6))
        ctk.CTkLabel(fila, text="Ver:", font=estilos.fuente(12, "bold")).pack(
            side="left", padx=(2, 8))
        self.seg_filtro = ctk.CTkSegmentedButton(
            fila, values=list(FILTROS.keys()), command=lambda _v: self.refrescar())
        self.seg_filtro.set("Todos")
        self.seg_filtro.pack(side="left")

    # ------------------------------------------------------------------
    def _construir_tabla(self):
        cont = ctk.CTkFrame(self, corner_radius=12)
        cont.grid(row=2, column=0, sticky="nsew", padx=(4, 10))
        cont.grid_rowconfigure(0, weight=1)
        cont.grid_columnconfigure(0, weight=1)

        estilos.estilizar_treeview()
        cols = ("Nombre", "Apellido", "Telefono", "Estado")
        self.tree = ttk.Treeview(cont, columns=cols, show="headings",
                                 style="Kelly.Treeview", selectmode="browse")
        for col, etiqueta, ancho in (("Nombre", "Nombre", 140),
                                     ("Apellido", "Apellido", 140),
                                     ("Telefono", "Teléfono", 110),
                                     ("Estado", "Estado", 120)):
            self.tree.heading(col, text=etiqueta)
            self.tree.column(col, width=ancho, anchor="w")

        vsb = ttk.Scrollbar(cont, orient="vertical", command=self.tree.yview,
                            style="Kelly.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=6)
        vsb.grid(row=0, column=1, sticky="ns", pady=6, padx=(0, 6))

        modo = ctk.get_appearance_mode()
        self.tree.tag_configure("par", background=estilos._lado(estilos.FONDO, modo))
        self.tree.tag_configure("temporal", foreground=estilos.AMBAR)
        self.tree.tag_configure("definitiva",
                                foreground=estilos._lado(estilos.TEXTO_TENUE, modo))
        self.tree.bind("<<TreeviewSelect>>", self._al_seleccionar)

        self.lbl_conteo = ctk.CTkLabel(cont, text="", font=estilos.fuente(11),
                                       text_color=estilos.TEXTO_TENUE)
        self.lbl_conteo.grid(row=1, column=0, columnspan=2, sticky="w",
                             padx=10, pady=(0, 6))

    # ------------------------------------------------------------------
    def _construir_formulario(self):
        panel = ctk.CTkScrollableFrame(self, corner_radius=12, label_text="Trabajador")
        panel.grid(row=2, column=1, sticky="nsew", padx=(0, 4))
        panel.grid_columnconfigure(0, weight=1)

        self.campos = {}
        for nombre, etiqueta in (("Nombre", "Nombre *"),
                                 ("Apellido", "Apellido *"),
                                 ("Telefono", "Teléfono *")):
            ctk.CTkLabel(panel, text=etiqueta, anchor="w",
                         font=estilos.fuente(12, "bold")).grid(
                sticky="ew", padx=6, pady=(8, 0))
            w = ctk.CTkEntry(panel, height=34)
            w.grid(sticky="ew", padx=6, pady=(2, 4))
            w.bind("<KeyRelease>", lambda e: self._reset_dup())
            self.campos[nombre] = w

        ctk.CTkLabel(panel, text="Precio del menú (S/) *", anchor="w",
                     font=estilos.fuente(12, "bold")).grid(
            sticky="ew", padx=6, pady=(8, 0))
        self.e_precio = ctk.CTkEntry(panel, height=34)
        self.e_precio.insert(0, f"{db.precio_por_defecto():.2f}")
        self.e_precio.grid(sticky="ew", padx=6, pady=(2, 0))
        ctk.CTkLabel(panel, text="Al cambiarlo, rige desde la quincena actual; "
                                 "las anteriores no se tocan.",
                     font=estilos.fuente(10), wraplength=220, justify="left",
                     text_color=estilos.TEXTO_TENUE).grid(sticky="ew", padx=6, pady=(2, 4))

        self.lbl_situacion = ctk.CTkLabel(panel, text="", anchor="w",
                                          font=estilos.fuente(12, "bold"),
                                          wraplength=220, justify="left")
        self.lbl_situacion.grid(sticky="ew", padx=6, pady=(8, 0))

        botones = ctk.CTkFrame(panel, fg_color="transparent")
        botones.grid(sticky="ew", pady=12)
        botones.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(botones, text="＋ Nuevo", command=self.nuevo,
                      fg_color=estilos.AMBAR, hover_color=estilos.AMBAR_HOVER,
                      text_color="#20302A").grid(row=0, column=0, sticky="ew", pady=3)
        ctk.CTkButton(botones, text="💾 Guardar", command=self.guardar).grid(
            row=1, column=0, sticky="ew", pady=3)
        self.btn_accion = ctk.CTkButton(botones, text="Dar de baja",
                                        command=self._accion_estado)
        self.btn_accion.grid(row=2, column=0, sticky="ew", pady=3)

        self.lbl_msj = ctk.CTkLabel(panel, text="Para un alta nueva solo escribe "
                                                "nombre, apellido y teléfono.",
                                    font=estilos.fuente(11), wraplength=220,
                                    justify="left",
                                    text_color=estilos.TEXTO_TENUE)
        self.lbl_msj.grid(sticky="ew", padx=6, pady=(4, 8))
        self._reflejar_seleccion()

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------
    def refrescar(self):
        estado = FILTROS.get(self.seg_filtro.get())
        filas = db.listar_trabajadores(self.e_busqueda.get(), estado)
        self._filas = {f["id_trabajador"]: dict(f) for f in filas}
        self.tree.delete(*self.tree.get_children())
        for i, f in enumerate(filas):
            tags = ["par"] if i % 2 else []
            if f["Estado"] == db.ESTADO_TEMPORAL:
                tags.append("temporal")
            elif f["Estado"] == db.ESTADO_DEFINITIVA:
                tags.append("definitiva")
            self.tree.insert("", "end", iid=f["id_trabajador"],
                             values=(f["Nombre"], f["Apellido"],
                                     f["Telefono"], f["Estado"]),
                             tags=tuple(tags))
        self._actualizar_conteo(len(filas))
        if self._sel and not self.tree.exists(self._sel):
            self._sel = None
        self._reflejar_seleccion()

    def _actualizar_conteo(self, mostrados):
        c = db.contar_por_estado()
        activos = c.get(db.ESTADO_ACTIVO, 0)
        temp = c.get(db.ESTADO_TEMPORAL, 0)
        defi = c.get(db.ESTADO_DEFINITIVA, 0)
        self.lbl_conteo.configure(
            text=f"{mostrados} mostrados · {activos} activos · "
                 f"{temp} baja temporal · {defi} baja definitiva")

    def _al_seleccionar(self, _e=None):
        sel = self.tree.selection()
        if not sel or sel[0] == self._sel:
            return
        self._sel = sel[0]
        self._reset_dup()
        f = self._filas.get(self._sel, {})
        for campo, clave in (("Nombre", "Nombre"), ("Apellido", "Apellido"),
                             ("Telefono", "Telefono")):
            w = self.campos[campo]
            w.delete(0, "end")
            w.insert(0, f.get(clave, ""))
        self._precio_cargado = db.precio_trabajador_actual(self._sel)
        self.e_precio.delete(0, "end")
        self.e_precio.insert(0, f"{self._precio_cargado:.2f}")
        self._reflejar_seleccion()
        self._msj("Editando; cambia los datos y pulsa Guardar.")

    def _reflejar_seleccion(self):
        f = self._filas.get(self._sel) if self._sel else None
        if not f:
            self.lbl_situacion.configure(text="")
            self.btn_accion.configure(state="disabled", text="Dar de baja",
                                      fg_color=estilos.ROJO,
                                      hover_color=estilos.ROJO_HOVER)
            return
        estado = f["Estado"]
        if estado == db.ESTADO_ACTIVO:
            self.lbl_situacion.configure(text="Situación: Activo",
                                         text_color=estilos.POSITIVO)
            self.btn_accion.configure(state="normal", text="Dar de baja",
                                      fg_color=estilos.ROJO,
                                      hover_color=estilos.ROJO_HOVER)
        elif estado == db.ESTADO_TEMPORAL:
            self.lbl_situacion.configure(
                text="Situación: Baja temporal (DT)\n" + self._detalle_baja(f),
                text_color=estilos.AMBAR)
            self.btn_accion.configure(state="normal", text="Reactivar",
                                      fg_color=estilos.VERDE,
                                      hover_color=estilos.VERDE_HOVER)
        else:  # definitiva
            self.lbl_situacion.configure(
                text="Situación: Baja definitiva (retirado)\n" + self._detalle_baja(f),
                text_color=estilos.NEGATIVO)
            self.btn_accion.configure(state="disabled", text="No reactivable",
                                      fg_color=estilos.ROJO,
                                      hover_color=estilos.ROJO_HOVER)

    @staticmethod
    def _detalle_baja(f):
        partes = []
        if f.get("Fecha_Baja"):
            try:
                partes.append("Desde " + datetime.strptime(
                    f["Fecha_Baja"], "%Y-%m-%d").strftime("%d/%m/%Y"))
            except ValueError:
                partes.append("Desde " + str(f["Fecha_Baja"]))
        if f.get("Motivo_Baja"):
            partes.append("Motivo: " + f["Motivo_Baja"])
        return "  ·  ".join(partes) if partes else "Sin detalle registrado."

    # ------------------------------------------------------------------
    # Alta / edición
    # ------------------------------------------------------------------
    def nuevo(self):
        self._sel = None
        self.tree.selection_remove(self.tree.selection())
        for w in self.campos.values():
            w.delete(0, "end")
        self._precio_cargado = None
        self.e_precio.delete(0, "end")
        self.e_precio.insert(0, f"{db.precio_por_defecto():.2f}")
        self._reset_dup()
        self._reflejar_seleccion()
        self._msj("Alta nueva: completa los datos y pulsa Guardar.",
                  color=estilos.VERDE_HOVER)

    def _validar(self):
        datos = {c: w.get().strip() for c, w in self.campos.items()}
        if not datos["Nombre"] or not datos["Apellido"]:
            return None, "Escribe el nombre y el apellido."
        tel = datos["Telefono"]
        if not tel:
            return None, "Escribe el teléfono."
        if not tel.isdigit() or not (6 <= len(tel) <= 9):
            return None, "El teléfono debe tener solo números (6 a 9 dígitos)."
        return datos, None

    def guardar(self):
        datos, error = self._validar()
        if error:
            self._msj("⚠ " + error, color=estilos.ROJO)
            return
        try:
            precio = round(float(self.e_precio.get().strip().replace(",", ".")), 2)
            if precio <= 0:
                raise ValueError
        except ValueError:
            self._msj("⚠ Escribe el precio del menú en soles, por ejemplo 8.00.",
                      color=estilos.ROJO)
            return
        # Aviso de posible duplicado por teléfono (requiere confirmar).
        otro = db.telefono_existe(datos["Telefono"], excluir_id=self._sel)
        if otro and not self._dup_confirmado:
            self._dup_confirmado = True
            self._msj(f"⚠ El teléfono ya lo usa {otro['Nombre']} {otro['Apellido']}. "
                      "Si es otra persona, pulsa Guardar otra vez para continuar.",
                      color=estilos.AMBAR)
            return

        nombre = f"{datos['Nombre']} {datos['Apellido']}"
        try:
            if self._sel:
                db.actualizar("Trabajador", datos, {"id_trabajador": self._sel})
                # El precio solo se re-registra si cambió (para no crear filas de
                # más). Rige desde el inicio de la quincena en curso: así se
                # refleja de inmediato sin tocar las quincenas ya pasadas.
                if self._precio_cargado is None or \
                        abs(precio - self._precio_cargado) > 0.005:
                    db.fijar_precio_trabajador(self._sel, precio,
                                               desde=db.inicio_quincena_vigente())
                msj = f"Datos de {nombre} actualizados."
            else:
                self._sel = db.alta_trabajador(
                    datos["Nombre"], datos["Apellido"], datos["Telefono"],
                    precio=precio)
                msj = f"{nombre} dado de alta (menú S/ {precio:.2f})."
        except Exception as e:
            self._msj(f"⚠ No se pudo guardar: {e}", color=estilos.ROJO)
            return
        self._reset_dup()
        self.refrescar()
        if self.tree.exists(self._sel):
            self.tree.selection_set(self._sel)
            self.tree.see(self._sel)
        self._reflejar_seleccion()
        self._msj(msj, color=estilos.VERDE_HOVER)

    # ------------------------------------------------------------------
    # Baja / reactivación
    # ------------------------------------------------------------------
    def _accion_estado(self):
        f = self._filas.get(self._sel) if self._sel else None
        if not f:
            return
        if f["Estado"] == db.ESTADO_ACTIVO:
            self._dialogo_baja(f)
        elif f["Estado"] == db.ESTADO_TEMPORAL:
            self._reactivar(f)

    def _reactivar(self, f):
        nombre = f"{f['Nombre']} {f['Apellido']}"
        if not messagebox.askyesno("Reactivar",
                                   f"¿Reincorporar a {nombre}? Volverá a estar "
                                   "disponible para anotarle raciones."):
            return
        db.reactivar_trabajador(self._sel)
        sel = self._sel
        self.refrescar()
        if self.tree.exists(sel):
            self.tree.selection_set(sel)
        self._msj(f"{nombre} reactivado.", color=estilos.VERDE_HOVER)

    def _dialogo_baja(self, f):
        nombre = f"{f['Nombre']} {f['Apellido']}"
        deuda = db.deuda_trabajador(self._sel)

        dlg = ctk.CTkToplevel(self)
        dlg.title("Dar de baja")
        dlg.resizable(False, False)
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()
        v = self.winfo_toplevel()
        dlg.geometry(f"+{v.winfo_rootx() + 340}+{v.winfo_rooty() + 170}")

        m = ctk.CTkFrame(dlg, fg_color="transparent")
        m.pack(padx=22, pady=18)
        ctk.CTkLabel(m, text=f"Dar de baja a {nombre}",
                     font=estilos.fuente(17, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        ctk.CTkLabel(m, text="Tipo de baja", font=estilos.fuente(12, "bold")).grid(
            row=1, column=0, columnspan=2, sticky="w")
        seg = ctk.CTkSegmentedButton(m, values=["Temporal (DT)", "Definitiva"])
        seg.set("Temporal (DT)")
        seg.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(2, 8))

        lbl_explica = ctk.CTkLabel(m, font=estilos.fuente(11), justify="left",
                                   wraplength=340, text_color=estilos.TEXTO_TENUE)
        lbl_explica.grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 8))

        ctk.CTkLabel(m, text="Motivo", font=estilos.fuente(12, "bold")).grid(
            row=4, column=0, sticky="w")
        ctk.CTkLabel(m, text="Fecha (dd/mm/aaaa)",
                     font=estilos.fuente(12, "bold")).grid(row=4, column=1, sticky="w")
        e_motivo = ctk.CTkEntry(m, width=210, height=34,
                                placeholder_text="Ej: descanso médico, renuncia…")
        e_motivo.grid(row=5, column=0, sticky="ew", padx=(0, 10), pady=(2, 8))
        e_fecha = ctk.CTkEntry(m, width=130, height=34)
        e_fecha.insert(0, date.today().strftime("%d/%m/%Y"))
        e_fecha.grid(row=5, column=1, sticky="w", pady=(2, 8))

        if deuda > 0.005:
            ctk.CTkLabel(m, text=f"⚠ {nombre} debe {_soles(deuda)} en total. "
                                 "Considera cobrarle antes de darlo de baja.",
                         font=estilos.fuente(11, "bold"), justify="left",
                         wraplength=340, text_color=estilos.ROJO).grid(
                row=6, column=0, columnspan=2, sticky="w", pady=(0, 6))

        chk = ctk.CTkCheckBox(m, text="Confirmo el retiro definitivo (no se podrá reactivar)",
                              font=estilos.fuente(11))
        lbl_error = ctk.CTkLabel(m, text="", font=estilos.fuente(11),
                                 text_color=estilos.ROJO, wraplength=340, justify="left")
        lbl_error.grid(row=8, column=0, columnspan=2, sticky="w")

        def es_definitiva():
            return seg.get() == "Definitiva"

        def actualizar(_v=None):
            if es_definitiva():
                lbl_explica.configure(
                    text="Definitiva: se retira de la empresa para siempre. No "
                         "se le podrá anotar raciones ni reactivar.")
                chk.grid(row=7, column=0, columnspan=2, sticky="w", pady=(0, 6))
            else:
                lbl_explica.configure(
                    text="Temporal (DT): se ausenta por un tiempo. No se le "
                         "anotan raciones mientras tanto, pero puedes "
                         "reincorporarlo cuando vuelva.")
                chk.deselect()
                chk.grid_remove()
        seg.configure(command=actualizar)
        actualizar()

        def confirmar():
            definitiva = es_definitiva()
            motivo = e_motivo.get().strip()
            if definitiva and not motivo:
                lbl_error.configure(text="⚠ Indica el motivo del retiro definitivo.")
                return
            if definitiva and not chk.get():
                lbl_error.configure(text="⚠ Marca la casilla para confirmar el "
                                         "retiro definitivo.")
                return
            try:
                fecha = datetime.strptime(e_fecha.get().strip(),
                                          "%d/%m/%Y").date().isoformat()
            except ValueError:
                lbl_error.configure(text="⚠ La fecha debe ser dd/mm/aaaa.")
                return
            db.dar_baja(self._sel, definitiva, motivo, fecha)
            dlg.destroy()
            sel = self._sel
            self.refrescar()
            if self.tree.exists(sel):
                self.tree.selection_set(sel)
                self.tree.see(sel)
            tipo = "definitiva" if definitiva else "temporal"
            self._msj(f"{nombre} dado de baja ({tipo}). Su historial se conserva.",
                      color=estilos.AMBAR)

        botones = ctk.CTkFrame(m, fg_color="transparent")
        botones.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ctk.CTkButton(botones, text="Confirmar baja", height=36,
                      fg_color=estilos.ROJO, hover_color=estilos.ROJO_HOVER,
                      command=confirmar).pack(side="left")
        ctk.CTkButton(botones, text="Cancelar", height=36, width=100,
                      fg_color="transparent", border_width=1,
                      command=dlg.destroy).pack(side="left", padx=10)

    # ------------------------------------------------------------------
    def _limpiar_busqueda(self):
        self.e_busqueda.delete(0, "end")
        self.refrescar()

    def _reset_dup(self):
        self._dup_confirmado = False

    def _msj(self, texto, color=None):
        self.lbl_msj.configure(text=texto,
                               text_color=color or estilos.TEXTO_TENUE)
