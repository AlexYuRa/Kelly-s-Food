# -*- coding: utf-8 -*-
"""
Kelly's Food - Vista CRUD genérica
==================================
Un único componente reutilizable que, dado el nombre de una tabla, arma:
  * buscador de texto libre
  * tabla (ttk.Treeview) con scroll
  * formulario lateral para Agregar / Editar / Eliminar
  * validación básica (requeridos, tipos, claves foráneas)

Se configura leyendo la definición de la tabla en db.TABLAS, así no hay que
escribir una pantalla por tabla.
"""

from tkinter import ttk, messagebox

import customtkinter as ctk

import db
from ui import estilos


class VistaCRUD(ctk.CTkFrame):
    def __init__(self, master, tabla: str):
        super().__init__(master, fg_color="transparent")
        self.tabla = tabla
        self.meta = db.TABLAS[tabla]
        self.columnas = self.meta["columnas"]
        self.pk = self.meta["pk"]
        self.campos = {}          # nombre_columna -> widget de entrada
        self.pk_seleccionada = None

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._construir_barra()
        self._construir_tabla()
        self._construir_formulario()
        self.refrescar()

    # ------------------------------------------------------------------
    # Barra superior: título + buscador
    # ------------------------------------------------------------------
    def _construir_barra(self):
        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.grid(row=0, column=0, columnspan=2, sticky="ew", padx=4, pady=(4, 10))
        barra.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            barra, text=self.meta["titulo"],
            font=estilos.fuente(22, "bold"),
        ).grid(row=0, column=0, sticky="w")

        self.entrada_busqueda = ctk.CTkEntry(
            barra, placeholder_text="Buscar…", width=260, height=36,
        )
        self.entrada_busqueda.grid(row=0, column=1, sticky="e", padx=(0, 8))
        self.entrada_busqueda.bind("<Return>", lambda e: self.refrescar())

        ctk.CTkButton(
            barra, text="Buscar", width=90, height=36,
            command=self.refrescar,
        ).grid(row=0, column=2, sticky="e", padx=4)
        ctk.CTkButton(
            barra, text="Limpiar", width=90, height=36,
            fg_color="transparent", border_width=1,
            command=self._limpiar_busqueda,
        ).grid(row=0, column=3, sticky="e")

    # ------------------------------------------------------------------
    # Tabla
    # ------------------------------------------------------------------
    def _construir_tabla(self):
        cont = ctk.CTkFrame(self, corner_radius=12)
        cont.grid(row=1, column=0, sticky="nsew", padx=(4, 10))
        cont.grid_rowconfigure(0, weight=1)
        cont.grid_columnconfigure(0, weight=1)

        estilos.estilizar_treeview()
        cols = [c[0] for c in self.columnas]
        self.tree = ttk.Treeview(
            cont, columns=cols, show="headings",
            style="Kelly.Treeview", selectmode="browse",
        )
        for nombre, etiqueta, tipo, _req in self.columnas:
            self.tree.heading(nombre, text=etiqueta)
            ancho = 90 if tipo in ("entero",) else 130
            self.tree.column(nombre, width=ancho, anchor="w")

        vsb = ttk.Scrollbar(cont, orient="vertical", command=self.tree.yview,
                            style="Kelly.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=6)
        vsb.grid(row=0, column=1, sticky="ns", pady=6, padx=(0, 6))

        self.tree.tag_configure("par", background=estilos._lado(
            estilos.SUPERFICIE, ctk.get_appearance_mode()))
        self.tree.bind("<<TreeviewSelect>>", self._al_seleccionar)

        self.lbl_conteo = ctk.CTkLabel(
            cont, text="", font=estilos.fuente(11),
            text_color=estilos.TEXTO_TENUE,
        )
        self.lbl_conteo.grid(row=1, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 6))

    # ------------------------------------------------------------------
    # Formulario lateral
    # ------------------------------------------------------------------
    def _construir_formulario(self):
        panel = ctk.CTkScrollableFrame(self, corner_radius=12, label_text="Registro")
        panel.grid(row=1, column=1, sticky="nsew", padx=(0, 4))
        panel.grid_columnconfigure(0, weight=1)

        for nombre, etiqueta, tipo, req in self.columnas:
            marca = " *" if req else ""
            ctk.CTkLabel(
                panel, text=etiqueta + marca, anchor="w",
                font=estilos.fuente(12, "bold"),
            ).grid(sticky="ew", padx=6, pady=(8, 0))

            # Combo para claves foráneas con pocos valores (p. ej. Metodo_Pago).
            fk = self.meta["fk"].get(nombre)
            if fk and self._pocos_valores(fk[0], fk[1]):
                valores = db.valores_columna(fk[0], fk[1])
                w = ctk.CTkComboBox(panel, values=valores, height=34)
                w.set("")
            else:
                w = ctk.CTkEntry(panel, height=34)
            w.grid(sticky="ew", padx=6, pady=(2, 4))

            # La PK autoincremental no se edita manualmente.
            if self.meta["auto"] and nombre in self.pk:
                w.configure(state="disabled")
            self.campos[nombre] = w

        botones = ctk.CTkFrame(panel, fg_color="transparent")
        botones.grid(sticky="ew", pady=12)
        botones.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(botones, text="＋ Nuevo", command=self.nuevo,
                      fg_color=estilos.AMBAR, hover_color=estilos.AMBAR_HOVER,
                      text_color="#20302A").grid(row=0, column=0, columnspan=2, sticky="ew", pady=3)
        ctk.CTkButton(botones, text="💾 Guardar", command=self.guardar).grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=3)
        ctk.CTkButton(botones, text="🗑 Eliminar", command=self.eliminar,
                      fg_color=estilos.ROJO, hover_color=estilos.ROJO_HOVER).grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=3)

        self.lbl_estado = ctk.CTkLabel(panel, text="", font=estilos.fuente(11),
                                       wraplength=220, justify="left")
        self.lbl_estado.grid(sticky="ew", padx=6, pady=(4, 8))

    def _pocos_valores(self, tabla, columna, umbral=30):
        try:
            return len(db.valores_columna(tabla, columna)) <= umbral
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------
    def refrescar(self):
        busqueda = self.entrada_busqueda.get()
        filas = db.listar(self.tabla, busqueda)
        self.tree.delete(*self.tree.get_children())
        for i, fila in enumerate(filas):
            valores = [fila[c[0]] for c in self.columnas]
            self.tree.insert("", "end", values=valores,
                             tags=("par",) if i % 2 else ())
        self.lbl_conteo.configure(text=f"{len(filas)} registro(s) mostrados")

    def _al_seleccionar(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        valores = self.tree.item(sel[0], "values")
        self.pk_seleccionada = {}
        for (nombre, _et, _tp, _rq), valor in zip(self.columnas, valores):
            self._set_campo(nombre, valor)
            if nombre in self.pk:
                self.pk_seleccionada[nombre] = valor
        self.lbl_estado.configure(text="Editando registro seleccionado.",
                                  text_color=estilos.TEXTO_TENUE)

    def _set_campo(self, nombre, valor):
        w = self.campos[nombre]
        estaba = w.cget("state")
        w.configure(state="normal")
        if isinstance(w, ctk.CTkComboBox):
            w.set(str(valor))
        else:
            w.delete(0, "end")
            w.insert(0, str(valor))
        if estaba == "disabled":
            w.configure(state="disabled")

    def _leer_formulario(self) -> dict:
        datos = {}
        for nombre, _et, _tp, _rq in self.columnas:
            w = self.campos[nombre]
            datos[nombre] = w.get().strip()
        return datos

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def nuevo(self):
        self.pk_seleccionada = None
        self.tree.selection_remove(self.tree.selection())
        for nombre, _et, _tp, _rq in self.columnas:
            w = self.campos[nombre]
            estaba = w.cget("state")
            w.configure(state="normal")
            if isinstance(w, ctk.CTkComboBox):
                w.set("")
            else:
                w.delete(0, "end")
            if self.meta["auto"] and nombre in self.pk:
                w.configure(state="disabled")
            elif estaba == "disabled":
                w.configure(state="disabled")
        self.lbl_estado.configure(text="Nuevo registro: completa y pulsa Guardar.",
                                  text_color=estilos.VERDE_HOVER)

    def _validar(self, datos: dict):
        """Devuelve (datos_limpios, error). error=None si todo bien."""
        limpios = {}
        for nombre, etiqueta, tipo, req in self.columnas:
            # No enviamos la PK autoincremental.
            if self.meta["auto"] and nombre in self.pk:
                continue
            valor = datos.get(nombre, "").strip()
            if req and not valor:
                return None, f"El campo «{etiqueta}» es obligatorio."
            if not valor:
                limpios[nombre] = None
                continue
            # Tipos
            if tipo == "entero":
                if not valor.lstrip("-").isdigit():
                    return None, f"«{etiqueta}» debe ser un número entero."
                valor = int(valor)
            elif tipo == "decimal":
                try:
                    valor = float(valor)
                except ValueError:
                    return None, f"«{etiqueta}» debe ser un número."
            elif tipo == "fecha":
                if not self._fecha_valida(valor):
                    return None, f"«{etiqueta}» debe tener formato AAAA-MM-DD."
            # Claves foráneas
            fk = self.meta["fk"].get(nombre)
            if fk and not db.existe_fk(fk[0], fk[1], valor):
                return None, f"«{etiqueta}» = {valor} no existe en {fk[0]}."
            limpios[nombre] = valor
        return limpios, None

    @staticmethod
    def _fecha_valida(valor: str) -> bool:
        from datetime import datetime
        try:
            datetime.strptime(valor, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    def guardar(self):
        datos = self._leer_formulario()
        limpios, error = self._validar(datos)
        if error:
            self._error(error)
            return
        try:
            if self.pk_seleccionada:  # actualizar
                db.actualizar(self.tabla, limpios, self.pk_seleccionada)
                msg = "Registro actualizado."
            else:                     # insertar
                nuevo_id = db.insertar(self.tabla, limpios)
                msg = f"Registro agregado (id {nuevo_id})." if self.meta["auto"] else "Registro agregado."
            self.refrescar()
            self.lbl_estado.configure(text=msg, text_color=estilos.VERDE_HOVER)
        except Exception as e:
            self._error(f"No se pudo guardar: {e}")

    def eliminar(self):
        if not self.pk_seleccionada:
            self._error("Selecciona primero un registro en la tabla.")
            return
        if not messagebox.askyesno("Confirmar eliminación",
                                   "¿Eliminar el registro seleccionado?"):
            return
        try:
            db.eliminar(self.tabla, self.pk_seleccionada)
            self.pk_seleccionada = None
            self.refrescar()
            self.nuevo()
            self.lbl_estado.configure(text="Registro eliminado.",
                                      text_color=estilos.AMBAR)
        except Exception as e:
            self._error(f"No se pudo eliminar: {e}")

    def _limpiar_busqueda(self):
        self.entrada_busqueda.delete(0, "end")
        self.refrescar()

    def _error(self, texto):
        self.lbl_estado.configure(text="⚠ " + texto, text_color=estilos.ROJO)
