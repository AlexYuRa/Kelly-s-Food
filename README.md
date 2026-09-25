# Kelly's Food — Sistema de gestión

Aplicación de escritorio para gestionar **Kelly's Food**, un negocio de venta de
menús (almuerzos) a los trabajadores de una empresa. Reemplaza el control en
cuaderno y Excel por una base de datos relacional normalizada y agrega un módulo
de ciencia de datos para pronosticar la demanda.

Proyecto del curso **Base de Datos Avanzada — Universidad Nacional de Trujillo (UNT)**.

**Tecnologías:** Python · SQLite · CustomTkinter · matplotlib · pandas · scikit-learn

---

## Funcionalidades

| Módulo | Qué hace |
|---|---|
| **Dashboard** | KPIs (ingresos, gastos, balance, raciones, trabajadores activos), ingresos vs. gastos por mes, top de trabajadores, pronóstico de demanda y niveles de demanda. Filtro por rango de fechas. |
| **Trabajadores** | Alta, edición, baja temporal/definitiva (lógica, sin borrar historial), reactivación y precio del menú por trabajador. |
| **Raciones** | Planilla por quincena (trabajadores × días), igual al Excel de la dueña. Panel lateral con resumen, cobro y deudas pendientes. |
| **Pagos** | Cobranza por quincena: a pagar, pagado y saldo de cada trabajador. |
| **Compras** | Registro de insumos comprados por nombre, con proveedor y costo. |
| **Menú** | Plato de cada día de la semana; semanas pasadas en solo lectura. |
| **Métodos de pago / Períodos de cobro** | Catálogos con CRUD y validaciones (quincenas sin cruces). |
| **Consultas / Reportes** | Consultas predefinidas con exportación a CSV o Excel. |

También incluye **tema claro/oscuro** conmutable desde la barra lateral.

La relación entre módulos y las reglas de integridad (baja de trabajadores, precio
con vigencia no retroactivo, raciones pagadas, etc.) están documentadas en
[Funcionalidades.md](Funcionalidades.md).

## Instalación y puesta en marcha

Requisitos: **Python 3.10 o superior** (probado en 3.13) y **Git**. En Windows,
al instalar Python deja marcada la opción *tcl/tk and IDLE* (trae `tkinter`).

```bash
# 1. Clonar el repositorio
git clone https://github.com/AlexYuRa/Kelly-s-Food.git
cd Kelly-s-Food

# 2. (Opcional) Crear un entorno virtual
py -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate

# 3. Instalar dependencias
py -m pip install -r requirements.txt

# 4. Ejecutar
py app.py
```

> En Linux/macOS usa `python3` en lugar de `py`.

La base de datos **`kellys_food.db` ya viene cargada** en el repositorio
(datos de prueba de marzo 2023 a julio 2026, ≈ 164 000 raciones), así que la app
abre directamente en el Dashboard. No hay que instalar ni configurar ningún
servidor de base de datos.

**Problemas comunes**

| Mensaje | Solución |
|---|---|
| `No module named 'customtkinter'` (u otro módulo) | Falta el paso 3. Si usas entorno virtual, actívalo antes. |
| `No module named 'tkinter'` | Reinstala Python con la opción *tcl/tk* (Linux: `sudo apt install python3-tk`). |
| `No existe la base de datos 'kellys_food.db'` | Ejecuta `py app.py` desde la carpeta del proyecto y verifica que el archivo se clonó. |
| El Dashboard no muestra pronóstico / niveles de demanda | Faltan `pandas`, `numpy` o `scikit-learn`: repite el paso 3. |

## Cómo ingresar datos

Todo se hace desde la barra lateral izquierda. Los montos van en soles con punto
decimal (`25.50`). Las fechas se escriben como **dd/mm/aaaa** en Trabajadores,
Raciones, Pagos y Compras, y como **AAAA-MM-DD** en Dashboard, Consultas y los
catálogos (Métodos de pago, Períodos de cobro). No hace falta conocer ningún ID:
en los módulos principales todo se busca por nombre.

El orden natural para registrar una quincena nueva es:

1. **Trabajadores → registrar clientes**
   - Pulsa **＋ Nuevo**, completa *Nombre*, *Apellido*, *Teléfono* y *Precio del
     menú (S/)*, y pulsa **💾 Guardar**. El sistema genera el código solo.
   - Para editar, selecciona a alguien de la lista, cambia los datos y guarda.
   - **Dar de baja** lo saca de las listas para nuevas raciones sin borrar su
     historial ni sus deudas. *Temporal* se puede reactivar; *Definitiva* no.

2. **Raciones → abrir la quincena**
   - Pulsa **＋ Nueva quincena**. Las fechas ya vienen sugeridas; puedes marcar
     *Empezar con los trabajadores de la quincena anterior*.
   - Usa ◀ ▶ o **Ir a hoy** para moverte entre quincenas.

3. **Raciones → anotar el consumo diario**
   - En **＋ Agregar trabajador** escribe parte del nombre y elige de la lista
     (solo aparecen trabajadores activos).
   - Haz **clic en la celda** del trabajador y el día, escribe la cantidad de
     menús y pulsa **Enter** (baja a la fila siguiente) o **Tab** (pasa al día
     siguiente). Deja la celda en `0` o vacía para quitar raciones.
   - Al hacer clic en el nombre, el panel derecho muestra lo que debe; desde ahí
     puedes **Registrar pago** o **Cambiar precio**.

4. **Pagos → cobrar**
   - Elige la quincena, selecciona al trabajador, escribe *Monto (S/)*, elige el
     *Método de pago* y la *Fecha*, y pulsa **💾 Registrar pago**.
   - *Mostrar solo los que deben* filtra la lista de deudores.

5. **Menú → plato del día** *(opcional)*
   - Escribe el plato en la tarjeta del día o elígelo de la lista; se guarda solo
     al pulsar Enter o salir de la casilla. Las semanas pasadas son de solo lectura.

6. **Compras → gastos en insumos**
   - Completa *Fecha*, *Proveedor*, *Insumo*, *Cantidad* y *Costo total (S/)*, y
     pulsa **💾 Guardar**. Si escribes un insumo que no existe, se crea (en kg).

7. **Métodos de pago / Períodos de cobro** son catálogos: **＋ Nuevo**, completar
   y **💾 Guardar**; seleccionar una fila para editarla o **🗑 Eliminar**.

8. **Revisar resultados**
   - **Dashboard**: escribe *Desde* / *Hasta* (AAAA-MM-DD) y pulsa **Aplicar**.
   - **Consultas / Reportes**: elige el reporte y el rango, pulsa **Ejecutar** y
     exporta con **⬇ Exportar Excel** o **⬇ Exportar CSV**.

> Los cambios se guardan al instante en `kellys_food.db`; no hay botón de
> "guardar todo". Para volver a los datos originales del repositorio:
> `git checkout -- kellys_food.db`.

## Estructura del proyecto

```
KellysFood/
├── app.py                 # Punto de entrada (ventana principal y navegación)
├── db.py                  # Capa de acceso a datos + reglas de negocio
├── kellys_food.db         # Base de datos SQLite ya cargada
├── construir_bd.py        # Reconstrucción de la BD (ver más abajo)
├── exportar_mysql.py      # Genera un backup .sql compatible con MySQL
├── ui/
│   ├── dashboard.py       # KPIs + gráficos + paneles de ML
│   ├── trabajadores_view.py
│   ├── raciones_view.py
│   ├── pagos_view.py
│   ├── compras_view.py
│   ├── menu_view.py
│   ├── crud_view.py       # CRUD genérico (catálogos)
│   ├── consultas.py       # Reportes + exportación CSV/Excel
│   └── estilos.py         # Paleta de marca y estilos
├── ml/
│   ├── datos.py           # Serie semanal + variables exógenas
│   ├── demanda.py         # Modelo en producción + sugerencia de compra
│   ├── segmentacion.py    # K-Means: niveles de demanda (descriptivo)
│   ├── cluster_semanas.py # K-Means de semanas sobre variables conocidas
│   └── pronostico.py      # SARIMAX + backtesting walk-forward
├── docs/
│   ├── sistema_prediccion_demanda.md
│   └── CONTEXTO_CLAUDE.md # Contexto para retomar el proyecto con Claude Code
├── Funcionalidades.md     # Documento funcional del sistema
├── Exposicion.md          # Guion de la exposición del curso
└── requirements.txt
```

## Base de datos

Sigue el **modelo físico normalizado** (25 tablas): `trabajador`,
`estado_trabajador`, `tel_trabajador`, `precio_trabajador`, `racion` +
`racion_relacional`, `pago`, `metodo_pago`, `periodo_cobro`, `menu`, y el
abastecimiento (`insumo`, `tipo_insumo`, `unidad_medida`, `receta` +
`receta_relacional`, `compra`, `detallecompra`, `compra_relacional`, `proveedor`,
`tel_proveedor`, `temporada`, `clasi_temporada`, `distrito`, `urbanizacion`).

`db.py` presenta estos datos a la interfaz sin que las pantallas tengan que
conocer la normalización. Los importes están en soles (S/).

### Backup en MySQL

La aplicación usa SQLite, pero se puede generar un volcado estilo `mysqldump`
(esquema + datos, InnoDB, utf8mb4) para importarlo en MySQL/MariaDB:

```bash
py exportar_mysql.py                 # genera backup_kellys_food_mysql.sql
py exportar_mysql.py otra_salida.sql
```

### Reconstruir la base de datos

`construir_bd.py` restaura `kellys_food.db` desde la copia maestra
`kellys_food_norm.db` o, en su defecto, desde los `.sql` mensuales de
`datos_sql/`. **Ninguna de esas fuentes se incluye en el repositorio**, así que
normalmente no hace falta: basta con el `kellys_food.db` versionado.

## Ciencia de datos

El módulo `ml/` analiza y pronostica la demanda semanal de raciones para
optimizar las compras. Los modelos complejos (SARIMAX con variables exógenas,
K-Means de semanas) se construyeron y **evaluaron por backtesting**; el modelo
adoptado en la app es un **promedio móvil de las 2 últimas semanas operativas**,
que obtuvo el menor error (≈ 6 % MAPE). Detalle completo en
[docs/sistema_prediccion_demanda.md](docs/sistema_prediccion_demanda.md).

## Generar un ejecutable .exe (opcional)

```bash
py -m pip install pyinstaller
py -m PyInstaller --onefile --windowed --add-data "kellys_food.db;." app.py
```

El ejecutable queda en `dist/app.exe`.
