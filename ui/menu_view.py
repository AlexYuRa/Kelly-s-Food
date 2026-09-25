# -*- coding: utf-8 -*-
"""
Kelly's Food - Menú semanal
===========================
Calendario de lunes a sábado (los domingos no se cocina): una tarjeta por día
con el plato. Se escribe o se elige uno de los platos ya conocidos y se
guarda solo. Vaciar la casilla borra el menú de ese día.
"""

from datetime import date, timedelta

import customtkinter as ctk

import db
from ui import estilos

NOMBRES_DIA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]


class VistaMenu(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self._lunes = self._lunes_de(date.today())
        self._valores = {}      # fecha_iso -> plato guardado
        self._combos = []       # un combo por día (lunes..sábado)
        self._titulos = []

        self.grid_columnconfigure(0, weight=1)
        self._construir_encabezado()
        self._construir_calendario()
        self._cargar()

    # ------------------------------------------------------------------
    def _construir_encabezado(self):
        ctk.CTkLabel(self, text="Menú de la semana",
                     font=estilos.fuente(24, "bold")).grid(
            row=0, column=0, sticky="w", padx=4, pady=(4, 8))

        barra = ctk.CTkFrame(self, corner_radius=12)
        barra.grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 12))
        fila = ctk.CTkFrame(barra, fg_color="transparent")
        fila.pack(fill="x", padx=12, pady=10)

        ctk.CTkButton(fila, text="◀", width=36, height=34,
                      command=lambda: self._mover(-1)).pack(side="left")
        self.lbl_semana = ctk.CTkLabel(fila, text="", width=260,
                                       font=estilos.fuente(14, "bold"))
        self.lbl_semana.pack(side="left", padx=8)
        ctk.CTkButton(fila, text="▶", width=36, height=34,
                      command=lambda: self._mover(1)).pack(side="left")
        ctk.CTkButton(fila, text="Ir a hoy", width=80, height=34,
                      fg_color="transparent", border_width=1,
                      command=self._ir_a_hoy).pack(side="left", padx=(10, 0))

        self.lbl_estado = ctk.CTkLabel(fila, text="", font=estilos.fuente(12),
                                       text_color=estilos.TEXTO_TENUE)
        self.lbl_estado.pack(side="right")

    def _construir_calendario(self):
        malla = ctk.CTkFrame(self, fg_color="transparent")
        malla.grid(row=2, column=0, sticky="nsew", padx=4)
        for c in range(3):
            malla.grid_columnconfigure(c, weight=1, uniform="dia")

        platos = db.platos_conocidos()
        for i, nombre_dia in enumerate(NOMBRES_DIA):
            card = ctk.CTkFrame(malla, corner_radius=14, fg_color=estilos.SUPERFICIE)
            card.grid(row=i // 3, column=i % 3, sticky="nsew", padx=6, pady=6)
            card.grid_columnconfigure(0, weight=1)

            titulo = ctk.CTkLabel(card, text=nombre_dia,
                                  font=estilos.fuente(14, "bold"))
            titulo.grid(row=0, column=0, sticky="w", padx=14, pady=(12, 0))
            self._titulos.append(titulo)

            combo = ctk.CTkComboBox(card, values=platos, height=36,
                                    font=estilos.fuente(13),
                                    command=lambda _v, i=i: self._guardar_dia(i))
            combo.set("")
            combo.grid(row=1, column=0, sticky="ew", padx=14, pady=(6, 4))
            combo.bind("<Return>", lambda _e, i=i: self._guardar_dia(i))
            combo.bind("<FocusOut>", lambda _e, i=i: self._guardar_dia(i))
            self._combos.append(combo)

            ctk.CTkLabel(card, text="Escribe el plato o elígelo de la lista",
                         font=estilos.fuente(10),
                         text_color=estilos.TEXTO_TENUE).grid(
                row=2, column=0, sticky="w", padx=14, pady=(0, 10))

    # ------------------------------------------------------------------
    def refrescar(self):
        """Recarga la semana y la lista de platos (se llama al mostrar la vista)."""
        platos = db.platos_conocidos()
        for combo in self._combos:
            combo.configure(values=platos)
        self._cargar()

    def _fechas_semana(self):
        return [(self._lunes + timedelta(days=i)).isoformat() for i in range(6)]

    def _cargar(self):
        fechas = self._fechas_semana()
        d1 = self._lunes.strftime("%d/%m")
        d2 = (self._lunes + timedelta(days=5)).strftime("%d/%m/%Y")
        self.lbl_semana.configure(text=f"Semana del {d1} al {d2}")

        self._valores = db.platos_semana(fechas[0], fechas[-1])
        hoy = date.today().isoformat()
        for i, fecha in enumerate(fechas):
            f = date.fromisoformat(fecha)
            es_hoy = fecha == hoy
            self._titulos[i].configure(
                text=f"{NOMBRES_DIA[i]} {f.strftime('%d/%m')}"
                     + ("  ·  HOY" if es_hoy else ""),
                text_color=estilos.AMBAR if es_hoy else estilos.TEXTO)
            self._combos[i].set(self._valores.get(fecha, ""))

        # Semanas pasadas: solo lectura (coherente con las quincenas cerradas).
        editable = self._semana_editable()
        for combo in self._combos:
            combo.configure(state="normal" if editable else "disabled")
        self.lbl_estado.configure(
            text="" if editable else "🔒 Semana pasada (solo lectura)",
            text_color=estilos.TEXTO_TENUE)

    def _semana_editable(self):
        """La semana se puede editar si aún no terminó (su sábado es hoy o
        futuro). Las semanas ya pasadas quedan de solo lectura."""
        sabado = (self._lunes + timedelta(days=5)).isoformat()
        return sabado >= date.today().isoformat()

    # ------------------------------------------------------------------
    def _guardar_dia(self, i):
        if not self._semana_editable():
            return
        fecha = self._fechas_semana()[i]
        plato = self._combos[i].get().strip()
        if plato == self._valores.get(fecha, ""):
            return
        try:
            db.fijar_plato(fecha, plato)
        except Exception as e:
            self.lbl_estado.configure(text=f"⚠ No se pudo guardar: {e}",
                                      text_color=estilos.ROJO)
            return
        f = date.fromisoformat(fecha).strftime("%d/%m")
        if plato:
            self._valores[fecha] = plato
            texto = f"Guardado: {NOMBRES_DIA[i]} {f} — {plato}"
            # Un plato nuevo pasa de inmediato a las sugerencias de todos los días.
            valores = list(self._combos[i].cget("values"))
            if plato not in valores:
                valores = sorted(valores + [plato])
                for combo in self._combos:
                    combo.configure(values=valores)
        else:
            self._valores.pop(fecha, None)
            texto = f"{NOMBRES_DIA[i]} {f} quedó sin menú."
        self.lbl_estado.configure(text=texto, text_color=estilos.TEXTO_TENUE)

    # ------------------------------------------------------------------
    def _mover(self, semanas):
        self._lunes += timedelta(weeks=semanas)
        self._cargar()

    def _ir_a_hoy(self):
        self._lunes = self._lunes_de(date.today())
        self._cargar()

    @staticmethod
    def _lunes_de(d):
        return d - timedelta(days=d.weekday())
