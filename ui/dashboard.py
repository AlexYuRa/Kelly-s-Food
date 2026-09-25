# -*- coding: utf-8 -*-
"""
Kelly's Food - Dashboard
========================
Panel de inicio: tarjetas KPI + gráficos (matplotlib embebido) con filtro por
rango de fechas. Ingresos = pagos de trabajadores; gastos = compras.
"""

import customtkinter as ctk
import matplotlib
matplotlib.use("Agg")  # backend seguro; usamos FigureCanvasTkAgg manualmente
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import db
from ui import estilos

try:
    from ml import demanda as ml_demanda
except Exception:  # noqa - si faltan dependencias, el dashboard sigue funcionando
    ml_demanda = None

try:
    from ml import segmentacion as ml_seg
except Exception:  # noqa
    ml_seg = None


class Dashboard(ctk.CTkScrollableFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self._lo, self._hi = db.rango_fechas()
        self._construir_encabezado()
        self._contenedor_kpis()
        self._contenedor_pronostico()
        self._contenedor_graficos()
        self._contenedor_demanda()
        self.recargar()

    # ------------------------------------------------------------------
    def _construir_encabezado(self):
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(4, 12))
        top.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(top, text="Resumen del negocio",
                     font=estilos.fuente(24, "bold")).grid(row=0, column=0, sticky="w")

        filtro = ctk.CTkFrame(top, fg_color="transparent")
        filtro.grid(row=0, column=1, sticky="e")
        ctk.CTkLabel(filtro, text="Desde", font=estilos.fuente(12)).pack(side="left", padx=(0, 4))
        self.e_desde = ctk.CTkEntry(filtro, width=110, height=32)
        self.e_desde.insert(0, self._lo or "")
        self.e_desde.pack(side="left", padx=(0, 10))
        ctk.CTkLabel(filtro, text="Hasta", font=estilos.fuente(12)).pack(side="left", padx=(0, 4))
        self.e_hasta = ctk.CTkEntry(filtro, width=110, height=32)
        self.e_hasta.insert(0, self._hi or "")
        self.e_hasta.pack(side="left", padx=(0, 10))
        ctk.CTkButton(filtro, text="Aplicar", width=90, height=32,
                      command=self.recargar).pack(side="left")

    def _contenedor_kpis(self):
        self.kpis = ctk.CTkFrame(self, fg_color="transparent")
        self.kpis.grid(row=1, column=0, sticky="ew")
        for i in range(4):
            self.kpis.grid_columnconfigure(i, weight=1, uniform="kpi")

    def _contenedor_pronostico(self):
        self.pronostico = ctk.CTkFrame(self, fg_color="transparent")
        self.pronostico.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        self.pronostico.grid_columnconfigure(0, weight=1)

    def _contenedor_graficos(self):
        self.graficos = ctk.CTkFrame(self, fg_color="transparent")
        self.graficos.grid(row=3, column=0, sticky="nsew", pady=(14, 4))
        self.graficos.grid_columnconfigure((0, 1), weight=1)

    def _contenedor_demanda(self):
        self.demanda = ctk.CTkFrame(self, fg_color="transparent")
        self.demanda.grid(row=4, column=0, sticky="nsew", pady=(6, 4))
        self.demanda.grid_columnconfigure((0, 1), weight=1)

    # ------------------------------------------------------------------
    def _tarjeta_kpi(self, col, titulo, valor, color=None, subtitulo=""):
        card = ctk.CTkFrame(self.kpis, corner_radius=14, fg_color=estilos.SUPERFICIE)
        card.grid(row=0, column=col, sticky="nsew", padx=6, pady=6)
        ctk.CTkLabel(card, text=titulo, font=estilos.fuente(12, "bold"),
                     text_color=estilos.TEXTO_TENUE).pack(anchor="w", padx=16, pady=(14, 2))
        ctk.CTkLabel(card, text=valor, font=estilos.fuente(26, "bold"),
                     text_color=color).pack(anchor="w", padx=16, pady=(0, 2))
        ctk.CTkLabel(card, text=subtitulo, font=estilos.fuente(11),
                     text_color=estilos.TEXTO_TENUE).pack(anchor="w", padx=16, pady=(0, 14))

    def _fmt_soles(self, v):
        return f"S/ {v:,.2f}"

    # ------------------------------------------------------------------
    def recargar(self):
        desde = self.e_desde.get().strip() or None
        hasta = self.e_hasta.get().strip() or None

        # KPIs
        for w in self.kpis.winfo_children():
            w.destroy()
        k = db.kpis(desde, hasta)
        self._tarjeta_kpi(0, "INGRESOS", self._fmt_soles(k["ingresos"]),
                          estilos.POSITIVO, "Pagos de trabajadores")
        self._tarjeta_kpi(1, "GASTOS", self._fmt_soles(k["gastos"]),
                          estilos.NEGATIVO, "Compras / insumos")
        color_bal = estilos.POSITIVO if k["balance"] >= 0 else estilos.NEGATIVO
        self._tarjeta_kpi(2, "BALANCE", self._fmt_soles(k["balance"]),
                          color_bal, "Ingresos − gastos")
        self._tarjeta_kpi(3, "RACIONES", f"{k['raciones']:,}",
                          estilos.AMBAR, f"{k['trabajadores']} trabajadores activos")

        # Panel de pronóstico (independiente del filtro de fechas: usa todo el histórico)
        self._panel_pronostico()

        # Gráficos
        for w in self.graficos.winfo_children():
            w.destroy()
        self._grafico_ingresos_gastos(desde, hasta)
        self._grafico_top_trabajadores(desde, hasta)

        # Sección de demanda (patrón histórico + segmentación K-Means).
        # Independiente del filtro: analiza toda la historia.
        self._seccion_demanda()

    # ------------------------------------------------------------------
    def _panel_pronostico(self):
        for w in self.pronostico.winfo_children():
            w.destroy()
        if ml_demanda is None:
            return
        try:
            d = ml_demanda.predecir_demanda()
            compra = ml_demanda.sugerir_compra(d["total_quincena"], top=8)
        except Exception:
            return
        if not d:
            return

        card = ctk.CTkFrame(self.pronostico, corner_radius=14,
                            fg_color=estilos.SUPERFICIE)
        card.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
        card.grid_columnconfigure(0, weight=0)
        card.grid_columnconfigure(1, weight=1)

        # --- Columna izquierda: la estimación ---
        izq = ctk.CTkFrame(card, fg_color="transparent")
        izq.grid(row=0, column=0, sticky="nw", padx=(18, 8), pady=16)
        ctk.CTkLabel(izq, text="🔮  PRÓXIMA QUINCENA",
                     font=estilos.fuente(12, "bold"),
                     text_color=estilos.TEXTO_TENUE).pack(anchor="w")
        ctk.CTkLabel(izq, text=f"~{d['total_quincena']:,} raciones",
                     font=estilos.fuente(28, "bold"),
                     text_color=estilos.AMBAR).pack(anchor="w", pady=(2, 0))
        ctk.CTkLabel(izq, text=f"{d['por_semana']:,}/semana  "
                              f"(entre {d['min_semana']:,} y {d['max_semana']:,})",
                     font=estilos.fuente(12),
                     text_color=estilos.TEXTO_TENUE).pack(anchor="w")
        ctk.CTkLabel(izq, text=f"Semana del {d['semana_desde']}",
                     font=estilos.fuente(11),
                     text_color=estilos.TEXTO_TENUE).pack(anchor="w", pady=(6, 0))
        ctk.CTkLabel(izq, text="Estimado con el promedio de las\n"
                              "2 últimas semanas de venta.",
                     font=estilos.fuente(10), justify="left",
                     text_color=estilos.TEXTO_TENUE).pack(anchor="w", pady=(8, 0))

        # --- Columna derecha: sugerencia de compra por insumo ---
        der = ctk.CTkFrame(card, fg_color="transparent")
        der.grid(row=0, column=1, sticky="nsew", padx=(8, 18), pady=16)
        der.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="ins")
        ctk.CTkLabel(der, text="Insumos a comprar (aprox.)",
                     font=estilos.fuente(12, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))
        if compra is not None and not compra.empty:
            for i, (_, r) in enumerate(compra.iterrows()):
                fila, col = divmod(i, 4)
                chip = ctk.CTkFrame(der, corner_radius=8, fg_color=estilos.FONDO)
                chip.grid(row=1 + fila, column=col, sticky="ew", padx=4, pady=4)
                ctk.CTkLabel(chip, text=r["insumo"], font=estilos.fuente(11, "bold")
                             ).pack(anchor="w", padx=10, pady=(6, 0))
                ctk.CTkLabel(chip, text=f"{r['cantidad']:,.0f} {r['unidad'].lower()}",
                             font=estilos.fuente(13), text_color=estilos.VERDE
                             ).pack(anchor="w", padx=10, pady=(0, 6))
            ctk.CTkLabel(der, text="Cantidades derivadas de las recetas "
                                  "(incluyen merma).",
                         font=estilos.fuente(10),
                         text_color=estilos.TEXTO_TENUE).grid(
                row=99, column=0, columnspan=4, sticky="w", pady=(6, 0))

    # ------------------------------------------------------------------
    def _figura(self):
        modo = ctk.get_appearance_mode()
        fondo = estilos._lado(estilos.SUPERFICIE, modo)
        texto = estilos._lado(estilos.TEXTO, modo)
        fig = Figure(figsize=(5.2, 3.2), dpi=100)
        fig.patch.set_facecolor(fondo)
        ax = fig.add_subplot(111)
        ax.set_facecolor(fondo)
        for spine in ax.spines.values():
            spine.set_color(texto)
            spine.set_alpha(0.2)
        ax.tick_params(colors=texto, labelsize=8)
        ax.title.set_color(texto)
        ax.yaxis.label.set_color(texto)
        return fig, ax, texto

    def _montar(self, fig, col):
        card = ctk.CTkFrame(self.graficos, corner_radius=14, fg_color=estilos.SUPERFICIE)
        card.grid(row=0, column=col, sticky="nsew", padx=6, pady=6)
        canvas = FigureCanvasTkAgg(fig, master=card)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)

    def _grafico_ingresos_gastos(self, desde, hasta):
        datos = db.ingresos_gastos_por_mes(desde, hasta)
        meses = [d["mes"] for d in datos]
        ingresos = [d["ingreso"] or 0 for d in datos]
        gastos = [d["gasto"] or 0 for d in datos]
        fig, ax, _ = self._figura()
        ax.plot(meses, ingresos, marker="o", ms=3, color=estilos.VERDE, label="Ingresos")
        ax.plot(meses, gastos, marker="o", ms=3, color=estilos.ROJO, label="Gastos")
        ax.fill_between(range(len(meses)), ingresos, color=estilos.VERDE, alpha=0.12)
        ax.set_title("Ingresos vs Gastos por mes", fontsize=11, fontweight="bold")
        self._espaciar_meses(ax, meses)
        ax.legend(fontsize=8, framealpha=0)
        fig.tight_layout()
        self._montar(fig, 0)

    def _grafico_top_trabajadores(self, desde, hasta):
        datos = db.top_trabajadores_raciones(8, desde, hasta)
        datos = list(reversed(datos))
        nombres = [d["nombre"] for d in datos]
        totales = [d["total"] for d in datos]
        fig, ax, texto = self._figura()
        barras = ax.barh(nombres, totales, color=estilos.AMBAR)
        ax.bar_label(barras, fontsize=7, color=texto, padding=2)
        ax.set_title("Top trabajadores por raciones", fontsize=11, fontweight="bold")
        fig.tight_layout()
        self._montar(fig, 1)

    @staticmethod
    def _espaciar_meses(ax, meses):
        # Muestra como máximo ~12 etiquetas en el eje X para que no se amontonen.
        n = len(meses)
        paso = max(1, n // 12)
        ax.set_xticks(range(0, n, paso))
        ax.set_xticklabels([meses[i] for i in range(0, n, paso)], rotation=45, ha="right")

    # ------------------------------------------------------------------
    # Sección de demanda: patrón histórico + segmentación K-Means
    # ------------------------------------------------------------------
    _COLOR_NIVEL = None  # se resuelve con estilos al usarse

    def _seccion_demanda(self):
        for w in self.demanda.winfo_children():
            w.destroy()
        if ml_seg is None:
            return
        try:
            mv = [(r["mes"], r["total"]) for r in db.raciones_por_mes()]
            segm = ml_seg.segmentar_meses(mv)
            resumen = ml_seg.resumen_niveles(segm)
            ind = ml_seg.indicadores(mv)
        except Exception:
            return
        if not segm:
            return
        nivel_actual = segm[-1]["nivel"] if segm else "—"

        ctk.CTkLabel(self.demanda, text="Comportamiento de la demanda",
                     font=estilos.fuente(18, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=6, pady=(6, 2))

        self._grafico_demanda(segm)                        # fila 1 (full width)
        self._tabla_indicadores(ind, nivel_actual)         # fila 2, col 0
        self._tabla_niveles(resumen, nivel_actual)         # fila 2, col 1

    def _color_nivel(self, nivel):
        return {"Alta": estilos.POSITIVO, "Media": estilos.AMBAR,
                "Baja": estilos.ROJO}.get(nivel, estilos.TEXTO_TENUE)

    def _grafico_demanda(self, segm):
        card = ctk.CTkFrame(self.demanda, corner_radius=14, fg_color=estilos.SUPERFICIE)
        card.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=6, pady=6)
        meses = [r["mes"] for r in segm]
        vals = [r["raciones"] for r in segm]
        colores = [self._color_nivel(r["nivel"]) for r in segm]
        fig, ax, texto = self._figura()
        ax.bar(range(len(meses)), vals, color=colores)
        ax.set_title("Raciones por mes — por nivel de demanda "
                     "(Alta / Media / Baja)", fontsize=11, fontweight="bold")
        self._espaciar_meses(ax, meses)
        # Leyenda de niveles.
        import matplotlib.patches as mpatches
        handles = [mpatches.Patch(color=self._color_nivel(n), label=n)
                   for n in ("Alta", "Media", "Baja")]
        ax.legend(handles=handles, fontsize=8, framealpha=0)
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=card)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)

    def _tabla_indicadores(self, ind, nivel_actual):
        card = ctk.CTkFrame(self.demanda, corner_radius=14, fg_color=estilos.SUPERFICIE)
        card.grid(row=2, column=0, sticky="nsew", padx=6, pady=6)
        card.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(card, text="Indicadores de la demanda",
                     font=estilos.fuente(13, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(12, 6))
        tend = ind.get("tendencia_pct", 0)
        signo = "▲" if tend > 0 else ("▼" if tend < 0 else "→")
        pares = [
            ("Promedio mensual", f"{ind.get('promedio', 0):,} raciones"),
            ("Mes pico", f"{ind.get('pico_mes', '—')}  ({ind.get('pico_val', 0):,})"),
            ("Mes más bajo", f"{ind.get('bajo_mes', '—')}  ({ind.get('bajo_val', 0):,})"),
            ("Tendencia (últ. 6m)", f"{signo} {abs(tend)}%"),
            ("Variabilidad (CV)", f"{ind.get('variabilidad_pct', 0)}%"),
            ("Meses analizados", f"{ind.get('meses', 0)}"),
        ]
        for i, (k, v) in enumerate(pares, start=1):
            ctk.CTkLabel(card, text=k, font=estilos.fuente(12),
                         text_color=estilos.TEXTO_TENUE).grid(
                row=i, column=0, sticky="w", padx=14, pady=2)
            ctk.CTkLabel(card, text=v, font=estilos.fuente(12, "bold")).grid(
                row=i, column=1, sticky="e", padx=14, pady=2)
        ctk.CTkLabel(card, text="Nivel del mes más reciente:",
                     font=estilos.fuente(12), text_color=estilos.TEXTO_TENUE).grid(
            row=99, column=0, sticky="w", padx=14, pady=(8, 12))
        ctk.CTkLabel(card, text=nivel_actual, font=estilos.fuente(13, "bold"),
                     text_color=self._color_nivel(nivel_actual)).grid(
            row=99, column=1, sticky="e", padx=14, pady=(8, 12))

    def _tabla_niveles(self, resumen, nivel_actual):
        card = ctk.CTkFrame(self.demanda, corner_radius=14, fg_color=estilos.SUPERFICIE)
        card.grid(row=2, column=1, sticky="nsew", padx=6, pady=6)
        for c in range(4):
            card.grid_columnconfigure(c, weight=1)
        ctk.CTkLabel(card, text="Períodos por nivel de demanda",
                     font=estilos.fuente(13, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", padx=14, pady=(12, 6))
        cabeceras = ("Nivel", "Meses", "Promedio", "Rango")
        for c, h in enumerate(cabeceras):
            ctk.CTkLabel(card, text=h, font=estilos.fuente(11, "bold"),
                         text_color=estilos.TEXTO_TENUE).grid(
                row=1, column=c, sticky="w", padx=(14 if c == 0 else 4), pady=2)
        for i, r in enumerate(resumen, start=2):
            ctk.CTkLabel(card, text=f"● {r['nivel']}", font=estilos.fuente(12, "bold"),
                         text_color=self._color_nivel(r["nivel"])).grid(
                row=i, column=0, sticky="w", padx=14, pady=3)
            ctk.CTkLabel(card, text=str(r["meses"]), font=estilos.fuente(12)).grid(
                row=i, column=1, sticky="w", padx=4, pady=3)
            ctk.CTkLabel(card, text=f"{r['promedio']:,}", font=estilos.fuente(12)).grid(
                row=i, column=2, sticky="w", padx=4, pady=3)
            ctk.CTkLabel(card, text=f"{r['min']:,}–{r['max']:,}",
                         font=estilos.fuente(11)).grid(
                row=i, column=3, sticky="w", padx=4, pady=3)
        ctk.CTkLabel(card, text="Clasificación del consumo histórico por nivel "
                                "de demanda.",
                     font=estilos.fuente(10), text_color=estilos.TEXTO_TENUE,
                     wraplength=320, justify="left").grid(
            row=90, column=0, columnspan=4, sticky="w", padx=14, pady=(8, 12))
