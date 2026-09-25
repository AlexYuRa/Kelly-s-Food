# Kelly's Food — Funcionalidades del sistema y cómo se relacionan entre sí

Documento funcional del sistema de gestión de **Kelly's Food** (venta de menús a
trabajadores de una empresa). Explica **qué hace cada módulo** y, sobre todo,
**cómo un cambio en un módulo repercute en los demás** (por ejemplo, cuando se da
de baja a un trabajador y cómo eso afecta a Raciones, Pagos y al Dashboard).

Toda la información pasa por una única capa de datos ([db.py](db.py)) sobre una
base SQLite normalizada (`kellys_food.db`). Las vistas nunca tocan la BD
directamente: piden y guardan a través de `db.py`, lo que mantiene las reglas de
negocio en un solo lugar.

---

## 1. Mapa de módulos

| Módulo | Vista | Para qué sirve |
|---|---|---|
| **Dashboard** | [ui/dashboard.py](ui/dashboard.py) | Resumen del negocio: KPIs, ingresos/gastos, raciones, pronóstico y niveles de demanda. |
| **Trabajadores** | [ui/trabajadores_view.py](ui/trabajadores_view.py) | Alta, edición, baja (temporal/definitiva), reactivación y precio del menú por trabajador. |
| **Raciones** | [ui/raciones_view.py](ui/raciones_view.py) | Planilla por quincena: cuántos menús consumió cada trabajador por día. Panel lateral con resumen y deudas. |
| **Pagos** | [ui/pagos_view.py](ui/pagos_view.py) | Cobros por quincena: cuánto debe y cuánto pagó cada trabajador. |
| **Compras** | [ui/compras_view.py](ui/compras_view.py) | Registro de insumos comprados (por nombre, sin IDs). |
| **Menú** | [ui/menu_view.py](ui/menu_view.py) | Plato de cada día de la semana. |
| **Períodos de cobro** | CRUD | Definición de las quincenas (rangos de fechas). |
| **Métodos de pago** | CRUD | Catálogo de formas de pago (efectivo, Yape, etc.). |
| **Consultas / Reportes** | [ui/consultas.py](ui/consultas.py) | Exportación de datos a CSV/Excel. |

La navegación entre módulos está en [app.py](app.py:84).

---

## 2. Las entidades que conectan todo

Casi todas las interacciones giran en torno a tres cosas:

- **El trabajador** (`ID_Trabajador`, p. ej. `001ALCO`): es la llave que une
  raciones, pagos, deudas y precio. Tiene un **estado**: Activo, Baja temporal o
  Baja definitiva.
- **La quincena** (`periodo_cobro`): un rango de fechas *desde–hasta*. Las
  raciones, los pagos y las deudas siempre se leen "por quincena".
- **El precio del menú por trabajador** (`precio_trabajador`, con fecha de
  vigencia): decide cuánto vale cada ración de ese trabajador **en la fecha en
  que la consumió**.

Entender estas tres piezas explica el resto del documento.

---

## 3. Funcionalidad por módulo (y sus enlaces)

### 3.1 Trabajadores

Qué hace:

- **Alta** de un trabajador con nombre, apellido, teléfono y **precio del menú**
  ([db.alta_trabajador](db.py:696)). El sistema genera solo el `ID_Trabajador`.
- **Edición** de sus datos y de su precio.
- **Baja temporal** o **baja definitiva**, con motivo y fecha
  ([db.dar_baja](db.py:737)).
- **Reactivación** de un trabajador dado de baja
  ([db.reactivar_trabajador](db.py:744)).

Con qué se relaciona:

- **→ Raciones y Pagos:** solo los trabajadores **Activos** aparecen en el
  buscador para agregarlos a una planilla ([db.buscar_trabajadores](db.py:606)
  filtra por `ID_Estado = 1`). Ver §4.
- **→ Precio:** al fijar/cambiar el precio, este rige **desde la quincena en
  curso** y **no** reescribe las quincenas pasadas. Ver §5.

### 3.2 Raciones

Qué hace:

- Muestra la **planilla de una quincena**: filas por trabajador, columnas por
  día, con la cantidad de menús que consumió cada día
  ([db.raciones_quincena](db.py:539)).
- Permite **subir/bajar la cantidad** de un día; cada ración es una fila real en
  la tabla `racion` ([db.fijar_racion](db.py:554)).
- Panel lateral al seleccionar un trabajador: **resumen de la quincena** (raciones,
  a pagar, pagado, saldo), botón de **cobrar/registrar pago**, **cambiar precio** y
  la lista de **deudas pendientes por quincena**.

Con qué se relaciona:

- **→ Menú:** al registrar la primera ración de un día que no tenía menú, se crea
  un menú marcador `"Menú del día"` (la ración exige un menú por integridad).
  Al vaciar el día, si ese menú era el marcador automático, se limpia
  ([db.fijar_racion](db.py:580)).
- **→ Pagos:** las raciones son la base de "lo que debe" el trabajador. No se
  puede reducir por debajo de las **raciones ya pagadas** de ese día
  ([db.fijar_racion](db.py:571)).
- **← Trabajadores:** la planilla muestra el **estado** del trabajador para
  distinguir a los dados de baja. Ver §4.

### 3.3 Pagos

Qué hace:

- Muestra por quincena, para cada trabajador con consumo o pago: **raciones,
  a pagar, pagado y saldo** ([db.cobranza_quincena](db.py:838)).
- Registra un pago ([db.registrar_pago](db.py:916)) y **marca como pagadas** las
  raciones de esa quincena que el monto alcanza a cubrir.

Con qué se relaciona:

- **← Raciones × Precio:** "a pagar" = raciones de la quincena × **precio vigente
  al inicio de esa quincena**. Cambiar el precio hoy no altera lo que se debía en
  quincenas pasadas. Ver §5.
- **→ Deudas:** un pago reduce el **saldo** de esa quincena. La deuda total del
  trabajador es la suma de saldos > 0 ([db.deuda_trabajador](db.py:749),
  [db.deudas_pendientes](db.py:891)).

### 3.4 Compras

Qué hace:

- Registra compras de insumos **por nombre** (sin IDs), con fecha, cantidad,
  costo y proveedor ([db.registrar_compra](db.py:304)). Internamente son tres
  tablas (`compra` + `detallecompra` + `compra_relacional`), pero la clienta ve
  una sola operación.
- Si el insumo no existía, se crea automáticamente
  ([db._asegurar_insumo](db.py:278)).

Con qué se relaciona:

- **→ Dashboard:** los costos alimentan el KPI de **gastos** y el balance
  ([db.kpis](db.py:398)).
- **→ Temporada:** cada compra se asocia a su temporada según la fecha, para el
  análisis histórico ([db._temporada_de](db.py:347)).

### 3.5 Menú

Qué hace:

- Define el **plato de cada día** de la semana ([db.fijar_plato](db.py:965)).
- Las **semanas pasadas** quedan en solo lectura.

Con qué se relaciona:

- **↔ Raciones:** un día con raciones no puede quedarse sin menú (integridad). Si
  se borra el plato de un día que tiene raciones, se deja el marcador
  `"Menú del día"` en vez de eliminarlo ([db.fijar_plato](db.py:968)).

### 3.6 Períodos de cobro (quincenas)

Qué hace:

- Crea quincenas validando que **no se crucen** entre sí y que no duren más de un
  mes ([db.crear_quincena](db.py:495)).

Con qué se relaciona:

- **→ Todo:** define las ventanas *desde–hasta* que usan Raciones, Pagos, Deudas
  y el precio vigente. Es el "eje de tiempo" del negocio.

### 3.7 Dashboard

Qué hace:

- KPIs (ingresos, gastos, balance, raciones, **trabajadores activos**), evolución
  mensual, top de trabajadores, **pronóstico de demanda** y **niveles de demanda**
  (segmentación).

Con qué se relaciona:

- **← Todo:** es un espejo agregado. Trabajadores activos, ingresos por pagos,
  gastos por compras, raciones por consumo. Cualquier cambio en los módulos se
  refleja aquí al refrescar.

---

## 4. Caso central: dar de baja a un trabajador y su efecto en Raciones

Esta es la interacción por la que más se pregunta. La regla adoptada es:
**los dados de baja siguen VISIBLES en el historial, pero quedan BLOQUEADOS para
nuevas operaciones.** No se borra nada: la baja es lógica (un cambio de estado),
nunca física.

### 4.1 Baja temporal

Escenario: un trabajador se ausenta un tiempo (vacaciones, permiso).

Qué pasa en cada módulo:

- **Trabajadores:** su estado pasa a *Baja temporal*, con motivo y fecha
  ([db.dar_baja](db.py:737), `definitiva=False`).
- **Buscador (Raciones/Pagos):** **deja de aparecer** al buscar para agregarlo a
  una planilla, porque el buscador solo trae Activos
  ([db.buscar_trabajadores](db.py:612)). → No se le pueden registrar **nuevas**
  raciones.
- **Planilla de Raciones:** si ya tenía raciones en la quincena, **sigue
  apareciendo** en la planilla (la planilla se arma desde el consumo real, e
  incluye la columna Estado para distinguirlo). Su historial no se toca.
- **Pagos y Deudas:** **conserva sus deudas**. Si quedó debiendo quincenas
  anteriores, siguen figurando y **se le puede cobrar** aunque esté de baja
  (la deuda no depende del estado, sino del saldo). Esto es intencional: dar de
  baja a alguien no perdona lo que debe.

### 4.2 Baja definitiva ("baja total")

Escenario: el trabajador ya no vuelve.

Qué pasa:

- **Trabajadores:** estado *Baja definitiva* ([db.dar_baja](db.py:737),
  `definitiva=True`).
- El comportamiento frente a Raciones y Pagos es el **mismo** que la baja
  temporal: sale del buscador (no más raciones nuevas), permanece en el historial
  y **sus deudas siguen cobrables**. La diferencia es semántica (no se espera su
  regreso) y de conteo: no cuenta como *trabajador activo* en el Dashboard.

### 4.3 Reactivación

- ([db.reactivar_trabajador](db.py:744)) lo vuelve a *Activo*, limpia motivo y
  fecha de baja, y **vuelve a aparecer** en el buscador para registrarle
  raciones otra vez. Su historial y deudas se mantienen intactos.

### 4.4 Resumen del efecto de la baja

| Efecto | Baja temporal | Baja definitiva |
|---|---|---|
| Aparece en el buscador para nuevas raciones | ❌ No | ❌ No |
| Se le pueden registrar raciones nuevas | ❌ No | ❌ No |
| Historial de raciones previo | ✅ Se conserva y se ve | ✅ Se conserva y se ve |
| Deudas pendientes | ✅ Siguen y se pueden cobrar | ✅ Siguen y se pueden cobrar |
| Cuenta como "trabajador activo" (Dashboard) | ❌ No | ❌ No |
| Se puede reactivar | ✅ Sí | ✅ Sí |

> **Bug histórico corregido:** antes, al dar de baja a un trabajador, este
> **seguía apareciendo** como si estuviera activo. Ahora la baja se propaga: sale
> del buscador y la planilla lo marca con su estado real.

---

## 5. Caso central: cambiar el precio del menú

El precio es **por trabajador** y **con fecha de vigencia** (tabla
`precio_trabajador`). Esto conecta Trabajadores → Raciones → Pagos → Deudas de
forma no retroactiva.

Cómo funciona:

- Cada trabajador tiene un precio **desde una fecha**. Al cambiarlo (desde
  Trabajadores o desde el panel de Raciones), el nuevo precio rige **desde la
  quincena en curso** ([db.inicio_quincena_vigente](db.py:521)) y **no** reescribe
  las quincenas ya pasadas ([db.fijar_precio_trabajador](db.py:824)).
- "A pagar" y "saldo" de una quincena se calculan con el **precio vigente al
  inicio de esa quincena** ([db.cobranza_quincena](db.py:842),
  [db.precio_trabajador_en](db.py:810)), no con el precio de hoy.

Ejemplo: un trabajador pagaba S/7. En julio subes su menú a S/8.

- Las quincenas de mayo y junio siguen calculándose a **S/7** (lo que realmente
  debía entonces).
- La quincena de julio en adelante se calcula a **S/8**.
- Sus deudas antiguas **no** se inflan por el cambio de precio.

> Antes había una sola tarifa global (7/8 = antiguo/nuevo). Se migró a precio por
> trabajador con vigencia, sembrando el precio histórico de cada uno para que la
> cobranza pasada quedara **idéntica** a como estaba.

---

## 6. Flujo completo de una quincena (cómo encajan los módulos)

1. **Períodos de cobro:** se abre la quincena (rango de fechas).
2. **Menú:** se define el plato de cada día (opcional; si no, se usa el marcador).
3. **Raciones:** cada día se registra cuántos menús consumió cada trabajador
   **Activo**. Esto crea filas `racion` y, si hace falta, el menú del día.
4. **Pagos:** al cobrar, el sistema calcula lo que debe cada uno
   (raciones × precio vigente) y marca las raciones cubiertas como pagadas.
5. **Deudas:** lo que no se cobró queda como saldo pendiente de esa quincena y
   sigue al trabajador hasta que pague (aunque luego se dé de baja).
6. **Compras:** en paralelo, se registran los insumos comprados (gastos).
7. **Dashboard:** refleja todo lo anterior de forma agregada (ingresos vs.
   gastos, raciones, activos, pronóstico y niveles de demanda).

---

## 7. Reglas de integridad que evitan inconsistencias

Estas reglas están en la capa de datos y protegen la coherencia entre módulos:

- **No borrar raciones ya pagadas:** reducir la cantidad de un día por debajo de
  lo pagado se bloquea con un mensaje claro ([db.fijar_racion](db.py:571)).
- **Un día con raciones siempre tiene menú:** no se puede dejar huérfana una
  ración; se usa el marcador `"Menú del día"`
  ([db.fijar_racion](db.py:588), [db.fijar_plato](db.py:968)).
- **Quincenas sin cruces:** no se pueden crear períodos que se solapen
  ([db.crear_quincena](db.py:501)).
- **Baja lógica, no física:** dar de baja nunca borra al trabajador ni su
  historial; solo cambia su estado ([db.dar_baja](db.py:737)).
- **Precio no retroactivo:** cambiar el precio nunca altera quincenas pasadas
  ([db.fijar_precio_trabajador](db.py:824)).
- **Semanas/quincenas pasadas en solo lectura** en Menú, para no reescribir
  historia por accidente.

---

## 8. Diagrama de dependencias (texto)

```
Períodos de cobro ──(define ventanas de tiempo)──► Raciones, Pagos, Deudas, Precio
Trabajadores ──(estado Activo)──► Buscador ──► Raciones / Pagos
Trabajadores ──(precio con vigencia)──► Pagos (a pagar) ──► Deudas
Raciones ──(crea/borra menú marcador)──► Menú
Raciones (consumo) × Precio ──► Pagos (a pagar) ── (pago) ──► Deudas (saldo)
Compras ──(gastos)──► Dashboard (balance)
Todo lo anterior ──(agregado)──► Dashboard (KPIs, pronóstico, niveles de demanda)
```

En una frase: **el trabajador y la quincena son las llaves; el consumo (raciones)
por el precio vigente produce la deuda, el pago la reduce, y el Dashboard resume
el conjunto. Dar de baja bloquea lo nuevo pero preserva el historial y las
deudas.**
