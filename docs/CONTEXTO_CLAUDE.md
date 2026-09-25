# Contexto para Claude Code — Kelly's Food

> **Para qué sirve este archivo.** Claude Code guarda su memoria de proyecto en
> `C:\Users\<usuario>\.claude\projects\<ruta-del-proyecto>\memory\`, y esa
> carpeta depende de la **ruta** donde está el proyecto. Si el repositorio se
> clona en otra carpeta u otra PC, Claude empieza sin contexto. Este archivo
> resume ese contexto (actualizado el **25/09/2026**).
>
> **Cómo usarlo en una sesión nueva:** escribe a Claude
> *«Lee docs/CONTEXTO_CLAUDE.md y guarda en tu memoria lo que corresponda»*.

---

## 1. El proyecto en pocas líneas

- App de escritorio (**Python 3.13 + SQLite + CustomTkinter**) para gestionar
  **Kelly's Food**: una señora que vende menús a trabajadores de una empresa y
  antes llevaba todo en cuaderno + Excel.
- Curso **Base de Datos Avanzada — UNT**. Exposición de 3 estudiantes
  (descriptivo / predictivo / agrupamiento) → guion en [Exposicion.md](../Exposicion.md).
- Repositorio: <https://github.com/AlexYuRa/Kelly-s-Food> (rama `main`).
  Ruta original en la PC del autor: `C:\BD_Avan\KellysFood`.
- Los datos de `kellys_food.db` son **de prueba (sintéticos)**, no reales.
- Documentos: [README.md](../README.md) (instalación y uso),
  [Funcionalidades.md](../Funcionalidades.md) (cómo se relacionan los módulos),
  [sistema_prediccion_demanda.md](sistema_prediccion_demanda.md) (ML).

## 2. Quién usa la app y qué implica (regla de diseño n.º 1)

La **usuaria final es la clienta**, sin conocimientos técnicos. Por eso:

- **Nada de IDs visibles.** Todo por nombre (trabajadores, insumos, proveedores).
- **Raciones = su Excel:** planilla por quincena, filas = trabajadores, columnas
  = días (sin domingos), celdas = n.º de raciones.
- Fechas en **dd/mm/aaaa** en las vistas rediseñadas.
- El autor prefiere que Claude **proponga mejoras de forma proactiva** (que el
  sistema sea funcional, no solo que muestre datos).

## 3. Arquitectura

- `app.py` → ventana y navegación. `db.py` → **única** capa de datos: las vistas
  nunca tocan SQLite directamente. `db.py` es una **capa de mapeo** que esconde
  la normalización a las vistas.
- Vistas rediseñadas para la clienta: `trabajadores_view`, `raciones_view`,
  `pagos_view`, `compras_view`, `menu_view`. **Métodos de pago** y **Períodos de
  cobro** siguen con la CRUD genérica (`crud_view.py`) **por decisión del autor**:
  no rediseñarlas.
- BD: **modelo físico normalizado, 25 tablas** (24 del diagrama +
  `precio_trabajador`). Extensiones que **no** están en el diagrama:
  `trabajador.Es_Nuevo/Motivo_Baja/Fecha_Baja`,
  `periodo_cobro.Codigo/Fecha_Inicio/Fecha_Fin` (ej. `202303Q1`),
  `pago.ID_Trabajador` (atribución directa del pago, además de
  `racion.ID_Pago`),
  `Precio_Menu` (7/8, solo para sembrar el precio por defecto) y
  `precio_trabajador`.
- La clave del trabajador es **`ID_Trabajador`** (código propio, ej. `001ALCO`),
  **no** el DNI. Altas nuevas: `db.generar_id_trabajador` (correlativo +
  iniciales, ej. `1260TEPR`).

## 4. Reglas de negocio ya decididas (no cambiarlas sin preguntar)

- **Baja lógica, nunca física.** Dos tipos: `Baja temporal` (reactivable) y
  `Baja definitiva` (no reactivable, requiere motivo). Un trabajador de baja:
  sale del buscador de Raciones, se ve en gris «(de baja)» y **bloqueado** en la
  planilla, no se copia a la nueva quincena, pero **sus deudas siguen cobrables**
  en Pagos.
- **Precio por trabajador con fecha de vigencia** (`precio_trabajador`). Al
  cambiarlo rige **desde el inicio de la quincena en curso**
  (`db.inicio_quincena_vigente`); **nunca retroactivo**. «A pagar» de una
  quincena = raciones × precio vigente al inicio de esa quincena.
- **Quincenas pasadas y semanas de menú pasadas = solo lectura**
  (`_quincena_editable`, `_semana_editable`). Las deudas de quincenas cerradas sí
  se cobran desde el panel.
- **No se borran raciones ya pagadas**: `fijar_racion` lanza error
  («corrige el pago primero»).
- Un día con raciones siempre tiene menú (marcador `"Menú del día"`, que se
  limpia solo al quedar el día vacío).
- Deuda: **un solo criterio** en toda la app. `deuda_trabajador` = suma de
  `deudas_pendientes` (saldos > 0 por quincena).
- Validaciones: tope `MAX_RACIONES_DIA = 99`, el pago que supera el saldo pide
  confirmación, proveedor no listado = error, insumo nuevo se crea en kg.

## 5. Trampas técnicas ya resueltas (no reintroducirlas)

- **Panel lateral de Raciones:** es un `CTkScrollableFrame` con **árbol de
  widgets fijo**. Los slots de deuda (`TOPE_DEUDAS = 6`) se muestran y ocultan
  con `grid()` / `grid_remove()` y `.configure()`. **Nunca destruir y recrear
  hijos** dentro de un scrollable: el panel queda en blanco.
- El panel se desmapeaba al navegar entre quincenas. Arreglo:
  `grid_columnconfigure(1, weight=1, minsize=280)` en `VistaRaciones`. Regla: un
  `CTkScrollableFrame` en una celda de grid junto a un `Treeview` que se
  reconstruye **necesita `minsize`** en su columna.
- `estilos.fuente(size, weight)` solo acepta `normal` / `bold` (`italic` →
  `TclError`).
- Guardar `dict(row)`, no el `sqlite3.Row` (no tiene `.get()`).
- Hay combinaciones Nombre + Apellido repetidas → desambiguar con teléfono.

## 6. Ciencia de datos (`ml/`, todo de solo lectura, se calcula al vuelo)

- **Pronóstico:** se evaluó por **backtesting walk-forward**. SARIMAX (+
  temporada + clúster K-Means de semanas «1b») ≈ 16 % MAPE → **rechazado**.
  Modelo adoptado: **MA_2** (promedio de las 2 últimas semanas operativas)
  ≈ 6 % MAPE, en `ml/demanda.py` (solo pandas, para que la app arranque rápido).
  `ml/pronostico.py` guarda la evidencia (usa statsmodels).
- El clúster 1b se construye con variables **conocidas de antemano**
  (temporada + calendario), nunca con el consumo, para evitar fuga de datos.
- **Segmentación:** `ml/segmentacion.py`, K-Means k = 3 sobre raciones por mes
  (Baja / Media / Alta), de uso **descriptivo**. Se muestra en el Dashboard.
- **Sugerencia de compra:** raciones pronosticadas × consumo por ración según
  las recetas (con merma). Limitación: `detallecompra` solo cubre 6 de 30
  insumos, así que se ordena por cantidad y no por costo.
- Principio acordado: presentar la metodología **con honestidad**. Evaluar
  SARIMAX y descartarlo con evidencia es ciencia de datos válida.
- Ideas no hechas: segmentación de clientes (RFM), morosidad, abandono (churn),
  merma de insumos, modelar el n.º de trabajadores activos (causa de los saltos
  que el calendario no explica).

## 7. Datos y archivos

- `kellys_food.db` (≈ 18 MB) es la **única** fuente de verdad y está en el repo.
  Datos: marzo 2023 – julio 2026, ≈ 164 000 raciones, 3 960 trabajadores,
  81 quincenas en `periodo_cobro` (con huecos legítimos entre ellas: domingos y
  cierres de fin de año).
- **Ya no existen** `datos_sql/` ni `kellys_food_norm.db` (tampoco están en el
  repo): `construir_bd.py` **no puede reconstruir** la BD. No borrar
  `kellys_food.db`. Para restaurarla: `git checkout -- kellys_food.db`.
- `backup_kellys_food_mysql.sql` se regenera con `py exportar_mysql.py` (el
  informe pide MySQL, la app usa SQLite; el import en un MySQL real **no se ha
  probado**).

## 8. Pendientes conocidos

- Consultas / Reportes: aún muestran la columna «ID Trabajador» y piden fechas
  AAAA-MM-DD a mano.
- Dashboard: filtro de fechas AAAA-MM-DD a mano → convendría usar atajos
  («Este mes», «Este año»).
- Catálogos CRUD (Métodos de pago, Períodos de cobro): fechas AAAA-MM-DD.
- Botón de respaldo de la BD y exportar la planilla de Raciones a Excel.
- Menores: «Nueva quincena» no tiene tope inferior de fecha; `_indice_hoy` salta
  a la primera quincena si hoy cae en un hueco entre quincenas.

## 9. Cómo prefiere trabajar el autor

- **No tomar capturas de pantalla** de la app. Verificar la UI con pruebas
  programáticas (asserts sobre widgets y datos). El autor juzga la estética.
- **No ensuciar la BD** al probar: usar una transacción con `rollback`, o datos
  con fecha ficticia (`2099-01-01`) y limpiarlos en un `finally`.
- Conversación en **español**.

## 10. Configuración de Claude Code

- **Python:** `py` (3.13) o
  `~/AppData/Local/Programs/Python/Python313/python.exe`. En Git Bash, usar
  `PYTHONIOENCODING=utf-8` para que se vean bien las tildes.
- **Comandos útiles:**
  ```bash
  py app.py                              # ejecutar la app
  py -m ml.demanda                       # probar el pronóstico
  PYTHONIOENCODING=utf-8 py -m ml.pronostico   # backtesting SARIMAX
  py exportar_mysql.py                   # backup MySQL
  ```
- **`.claude/settings.local.json`** (no se versiona, está en `.gitignore`): solo
  tenía permisos para scripts puntuales de sesiones anteriores. Para la nueva
  carpeta basta con algo así:
  ```json
  {
    "permissions": {
      "allow": [
        "Bash(py *)",
        "Bash(PYTHONIOENCODING=utf-8 py *)",
        "PowerShell(py *)"
      ]
    }
  }
  ```
- **Memoria de Claude:** en la ruta original está en
  `C:\Users\USERJSSV\.claude\projects\c--BD-Avan-KellysFood\memory\`. Si se
  clona en `C:\BD_Avan\KellysFood`, esa memoria se vuelve a enlazar sola.
