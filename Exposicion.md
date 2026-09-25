# Guion de Exposición (detallado) — Kelly's Food
### Sistema de gestión + ciencia de datos aplicada a la demanda

**Duración:** ~15 min · **3 estudiantes** · Cada uno defiende **su área completa**
(funcionalidad → objetivo → variables → modelo/tendencia → resultados).

**Cómo leer este guion:**
- El texto **entre comillas** es lo que se dice (pueden adaptarlo a sus palabras).
- `[MOSTRAR: …]` = qué tener en pantalla en ese momento.
- `[SI PREGUNTAN: …]` = respuesta lista por si el profesor interrumpe.

| Estudiante | Área | Tipo de ciencia de datos |
|-----------|------|--------------------------|
| **1** | Registro y consumo | **Descriptivo** (análisis exploratorio / indicadores) |
| **2** | Predicción y compras | **Predictivo / supervisado** (pronóstico) |
| **3** | Análisis de la demanda | **Agrupamiento / no supervisado** (segmentación) |

---

# 👤 ESTUDIANTE 1 — Registro operativo y comportamiento del consumo

### Apertura *(15 s)*
> "Buenas tardes. Presentamos **Kelly's Food**, un sistema hecho para un negocio
> real: la venta de menús —almuerzos— a los trabajadores de una empresa
> agroindustrial. La dueña llevaba todo en un **cuaderno y un Excel**. Nosotros lo
> convertimos en un sistema con **base de datos** y, encima, le aplicamos **ciencia
> de datos**. Yo voy a explicar el **registro del negocio** y el **análisis del
> consumo**."

### 1) Funcionalidad *(≈1.5 min)*  `[MOSTRAR: la app abierta]`
> "El sistema tiene varios módulos. Los principales son:"

- **Trabajadores** `[MOSTRAR: módulo Trabajadores]`
  > "Aquí se registran los clientes. Lo importante: la dueña **no ve códigos ni
  > IDs**, solo nombres. Cada trabajador tiene su **precio de menú**, porque unos
  > pagan 7 soles y otros 8. Y en vez de borrar a alguien, se le da de **baja**, así
  > no se pierde el historial."

- **Raciones** `[MOSTRAR: la planilla de Raciones]`
  > "Esta es la pantalla estrella: una **planilla idéntica a su Excel** —filas los
  > trabajadores, columnas los días de la quincena—. Se anota con un clic. Y cuando
  > selecciono a una persona `[hacer clic en un trabajador]`, aparece un **panel**
  > con su resumen: cuántas raciones pidió, cuánto debe, y **de qué quincenas
  > debe**. Desde ahí mismo se le puede **cobrar**."

- **Pagos y Menú** *(mencionar rápido)*
  > "También hay cobranza por quincena y un calendario de menús."

> "Y detrás de todo hay una **base de datos relacional normalizada** en SQLite, con
> **reglas de consistencia**: por ejemplo, si doy de baja a un trabajador, **deja de
> aparecer** para asignarle almuerzos; y una quincena ya cerrada queda de **solo
> lectura** para no alterar lo ya cobrado."

`[SI PREGUNTAN: ¿qué es normalizada?]`
> "Que la información no se repite: cada dato vive en una sola tabla y se relaciona
> con las demás por claves. Evita errores e inconsistencias."

### 2) Objetivo *(20 s)*
> "El objetivo de mi parte es doble: **digitalizar el control** del negocio y, sobre
> todo, **entender cómo se comporta el consumo**. En ciencia de datos, esto es la
> fase de **análisis exploratorio**: mirar bien los datos antes de predecir nada."

### 3) Variables *(20 s)*
> "Las variables que analizo son: las **raciones por período** —por día, por
> quincena y por mes—, los **pagos**, el **saldo o deuda** de cada trabajador y el
> **consumo por persona**."

### 4) Modelo / tendencia a aprender *(1 min)*  `[MOSTRAR: Dashboard → sección "Comportamiento de la demanda"]`
> "Mi 'modelo' es **descriptivo**: no predice todavía, **describe**. En el Dashboard,
> la sección *Comportamiento de la demanda* calcula **indicadores** a partir de toda
> la historia:"
- > "El **promedio mensual** de raciones."
- > "El **mes pico** y el **mes más bajo**."
- > "La **tendencia** de los últimos 6 meses —si el negocio sube o baja—."
- > "Y la **variabilidad**, que mide qué tan parejo o irregular es el consumo."

> "Esto es lo que en ciencia de datos se llama **EDA, análisis exploratorio de
> datos**: es el paso que **encuentra los patrones** que después usan los modelos
> de mis compañeros."

### 5) Resultados / conclusiones *(30 s)*
> "¿Qué encontramos? Que el consumo es un **nivel bastante estable pero con
> estacionalidad**: hay meses claramente altos y otros bajos, y una variabilidad
> importante. Ese hallazgo es justamente **la razón por la que vale la pena
> predecir y segmentar** la demanda, que es lo que explican mis compañeros."

### Reglas de negocio que cubre mi parte
> "Mi parte resuelve las reglas del **registro y la operación diaria**:"
- **RN1** (datos del trabajador), **RN2** (exclusividad Camposol), **RN3**
  (trabajador ↔ raciones), **RN4** (menú diario), **RN5** (registro de la ración),
  **RN6** (costo: menú + envío), **RN7** (periodicidad de cobro), **RN8** (métodos
  de pago).
> "Las resolvemos con los módulos de **Trabajadores, Raciones, Menú y Pagos**, y
> con el **modelo normalizado** que las respalda." *(Mapa completo al final.)*

> **Transición:** "Con estos patrones ya identificados, [nombre] explica cómo el
> sistema **predice** la demanda."

---

# 👤 ESTUDIANTE 2 — Predicción de la demanda y planificación de compras

### Apertura *(15 s)*
> "Gracias. Yo presento el **modelo predictivo**: cómo estimamos cuánta demanda
> habrá para **comprar la cantidad justa** de insumos."

### 1) Funcionalidad *(1 min)*  `[MOSTRAR: Dashboard → tarjeta de pronóstico]`
> "En el Dashboard tenemos una tarjeta que dice **'Próxima quincena: ~N
> raciones'**, con un rango estimado. Y debajo, la parte más útil para el
> negocio:" `[señalar los insumos]`
> "el sistema **traduce esa demanda a insumos**: cuántos kilos de arroz, de pollo,
> etc., hay que comprar. Y lo calcula usando las **recetas** e **incluyendo la
> merma**, que es lo que se pierde al cocinar."
> "También está el módulo **Compras** para registrar lo que se adquiere."

### 2) Objetivo *(20 s)*
> "El objetivo es **predecir la demanda** de la próxima quincena para **planificar
> las compras** y **reducir la merma**: ni comprar de más y que se malogre, ni
> comprar de menos y quedarse sin vender."

### 3) Variables *(50 s)*
> "Aquí hay que distinguir tres tipos de variables:"
- > "La **variable dependiente**, lo que queremos predecir: las **raciones por
  > semana**."
- > "Las **variables predictoras**, que nos ayudan a estimar: la **temporada**
  > —alta, media o baja demanda— y el **calendario** —el mes, las semanas de cierre
  > de fin de año, la reapertura, y la estacionalidad del año—."
- > "Y un principio importante: **evitar la fuga de datos**."

`[SI PREGUNTAN o para explicarlo: qué es fuga de datos]`
> "La **fuga de datos** es hacer trampa sin querer: usar para predecir algo que en
> la vida real solo se conoce **después**. Por eso solo usamos variables que se
> **conocen de antemano**, como el calendario y la temporada, nunca el consumo
> futuro."

### 4) Modelo / tendencia a aprender *(1 min)*
> "El modelo **aprende de más de 3 años** de historia. Probamos dos técnicas de
> verdad:"
- > "**SARIMAX**, un modelo de **series de tiempo** que usa la historia más esas
  > variables externas."
- > "y **K-Means** como apoyo, para agrupar semanas parecidas."

> "Pero lo más importante es **cómo lo validamos**: con **backtesting walk-forward**."

`[explicar el backtesting]`
> "El backtesting es como **rendir un examen con el pasado**: le tapamos al modelo
> lo que pasó, le pedimos que **prediga la siguiente quincena**, y comparamos con lo
> que realmente ocurrió. Repetimos eso muchas veces y medimos el error con una
> métrica llamada **MAPE**, que es el **porcentaje promedio de equivocación**."

### 5) Resultados / conclusiones *(50 s)*  `[MOSTRAR: la tabla de resultados o una diapositiva]`
> "Y aquí viene lo interesante, porque el resultado fue **honesto y contraintuitivo**:"

| Modelo | Error de una quincena típica (MAPE) |
|--------|-------------------------------------|
| **Promedio de las 2 últimas semanas (el que adoptamos)** | **≈ 6 %** |
| SARIMAX + temporada + calendario | ≈ 16 % |

> "El modelo **más simple** —un promedio de las dos últimas semanas— **le ganó** al
> SARIMAX, que es mucho más complejo. ¿Por qué? Porque la demanda es un nivel muy
> estable con saltos que el calendario no puede anticipar, y el modelo complejo
> **añadía ruido sin aportar**."
> "La conclusión es una lección de ciencia de datos: **no siempre lo más complejo
> es mejor**, y por eso hay que **medir con evidencia**, no elegir por moda. Nosotros
> dejamos funcionando el que **de verdad** predice mejor."

### Reglas de negocio que cubre mi parte
> "Mi parte resuelve las reglas de **abastecimiento**:"
- **RN10** (datos del proveedor), **RN11** (proveedor ↔ insumos), **RN12** (registro
  de insumos), **RN13** (perecible / no perecible), **RN14** (compras de insumos),
  **RN15** (receta del menú).
> "Son proveedores, insumos, compras y recetas. Y la **receta (RN15)** es,
> además, la que el sistema usa para **traducir la demanda en insumos a comprar**."

> **Transición:** "Y para saber **cuándo** hay más o menos demanda, [nombre] explica
> la segmentación."

---

# 👤 ESTUDIANTE 3 — Segmentación de la demanda

### Apertura *(15 s)*
> "Gracias. Yo presento el **modelo de agrupamiento**, que responde a otra pregunta:
> ¿cuáles son los **períodos de alta y baja demanda** del negocio? Y lo hace
> **solo**, aprendiendo de los datos."

### 1) Funcionalidad *(50 s)*  `[MOSTRAR: Dashboard → "Comportamiento de la demanda"]`
> "En el Dashboard mostramos un **gráfico de las raciones por mes**, pero con un
> detalle: cada barra está **coloreada según su nivel** —verde para demanda alta,
> ámbar para media, rojo para baja—." `[señalar el gráfico]`
> "Y al lado, una **tabla de períodos por nivel**. Así la dueña ve, de un vistazo,
> **cuáles son sus temporadas** fuertes y flojas."

### 2) Objetivo *(20 s)*
> "El objetivo es **identificar los períodos de alta, media y baja demanda** para
> tomar decisiones: cuándo comprar más, cuándo necesita más personal, cuándo
> reforzar la cobranza."

### 3) Variables *(20 s)*
> "Las variables son simples pero suficientes: el **consumo mensual** —las raciones
> de cada mes— y el **nivel o grupo** que el modelo le asigna a cada mes."

### 4) Modelo / tendencia a aprender *(1 min)*
> "Aquí usamos **K-Means**, un algoritmo de **aprendizaje no supervisado**."

`[explicar K-Means]`
> "'No supervisado' significa que **nadie le dice** cuáles son las temporadas: el
> algoritmo **aprende solo**. K-Means **agrupa** los meses parecidos entre sí; le
> pedimos **3 grupos** y él encuentra los cortes naturales entre demanda baja, media
> y alta."
> "Un punto clave: aquí **sí** podemos agrupar por el consumo, porque es un análisis
> **descriptivo del pasado** —clasificamos lo que ya pasó—, así que **no hay fuga de
> datos**."

### 5) Resultados / conclusiones *(40 s)*  `[MOSTRAR: la tabla de niveles]`
> "El resultado son **tres niveles bien diferenciados**:"
- > "**Alta:** alrededor de **7.000 raciones al mes**."
- > "**Media:** unas **4.200**."
- > "**Baja:** unas **2.000**."

> "Y lo mejor es que estos grupos **coinciden con la estacionalidad agrícola** del
> negocio: los meses de campaña son los de demanda alta. Esto le da a la dueña una
> **guía objetiva**, basada en datos, de cuándo prepararse para vender más o menos."

### Reglas de negocio que cubre mi parte
> "Mi parte se apoya en la regla estacional:"
- **RN9** (clasificación estacional: la **temporada** —Alta/Baja— con fecha de
  inicio y fin, que agrupa las compras).
> "El sistema clasifica el año en **niveles de demanda**, que es justo lo que mi
> segmentación identifica y muestra."

### Cierre del grupo *(20 s)*
> "En resumen: primero **registramos y entendimos** el consumo, luego **aprendimos a
> predecirlo**, y finalmente lo **segmentamos** en temporadas. Tres tipos de ciencia
> de datos trabajando sobre un negocio real. Muchas gracias. ¿Alguna pregunta?"

---

## Mapa de Reglas de Negocio (RN1–RN15)

> **Cómo presentarlo:** este es un curso de **Base de Datos**, así que lo central es
> que el **modelo normalizado capture cada regla**. La mayoría se cumple del todo;
> unas pocas están **soportadas por el modelo** (los campos existen) con alcance
> limitado en esta versión. Presentarlo así es honesto y sólido.

**Leyenda:** ✅ se cumple · ◑ soportado por el modelo, alcance limitado · ⚑ política.

| RN | Est. | Cómo se resuelve en el sistema | Estado |
|----|------|--------------------------------|--------|
| **RN1** | 1 | Tabla `trabajador` (nombres, apellidos, teléfono, estado) + módulo Trabajadores. Estado Activo / Baja (= Inactivo). | ✅ |
| **RN2** | 1 | Solo se registran trabajadores de Camposol; es una **política**, no una validación de software. | ⚑ |
| **RN3** | 1 | `racion_relacional`: cada ración pertenece a **un** trabajador; **varias** raciones por día. | ✅ |
| **RN4** | 1 | Tabla `menu` (fecha + descripción del plato) + módulo Menú. | ✅ |
| **RN5** | 1 | `racion` guarda Fecha_Entrega, **Estado_Despacho**, y vía `pago` el período y método. El campo Estado_Despacho existe; el flujo **Enviada/Cancelada** no está en la interfaz (hoy todo "Entregado"). | ◑ |
| **RN6** | 1 | `pago` separa **Monto_Menu** y **Monto_Envio** (dos cargos, tal como pide la regla). En esta versión el precio es por trabajador y el envío de S/1 no se cobra. | ◑ |
| **RN7** | 1 | `periodo_cobro` implementa el cobro **Quincenal**. La modalidad **Mensual** por trabajador no está implementada. | ◑ |
| **RN8** | 1 | Catálogo `metodo_pago` (Efectivo, Yape —y Plin—); cada pago queda **vinculado** al método. | ✅ |
| **RN9** | 3 | `temporada` + `clasi_temporada` (con Fecha_Inicio/Fecha_Fin) y `compra_relacional`. Usamos 3 niveles (Alta/Media/Baja). | ✅ |
| **RN10** | 2 | Tabla `proveedor` (RUC, nombre, contacto, dirección: calle/urbanización/distrito/número) + `tel_proveedor`. Sin **alta** de proveedor en la UI (decisión: son los de siempre). | ✅ modelo |
| **RN11** | 2 | Proveedor ↔ insumo (muchos a muchos) a través de las compras. | ✅ |
| **RN12** | 2 | `insumo` (nombre, unidad, fecha de venc.) + `detallecompra` (cantidad, costo) + `receta`. | ✅ |
| **RN13** | 2 | `tipo_insumo` clasifica los insumos (perecible / no perecible). La regla de compra diaria vs. por período no se **fuerza** en el sistema. | ◑ |
| **RN14** | 2 | `compra` (código único, fecha) + `compra_relacional` (proveedor) + `detallecompra` (insumos, monto). Módulo Compras. | ✅ |
| **RN15** | 2 | `receta` + `receta_relacional` (cantidad usada, unidad, por menú y fecha). **La usa el modelo de ciencia de datos** para calcular los insumos. | ✅ |

> **Si el profesor pregunta por las ◑ (RN5 Cancelada, RN6 envío S/1, RN7 Mensual,
> RN13 sourcing):** *"El modelo de datos ya las contempla —los campos y tablas
> existen—; en esta versión priorizamos el flujo real de la clienta (cobro
> quincenal, envío incluido). Activarlas no requiere rediseñar la base."* Es una
> respuesta honesta y que demuestra que **entienden su propio modelo**.

---

## Mapa de Requerimientos funcionales

| Requerimiento | Módulo / responsable | Est. |
|---------------|----------------------|------|
| Registrar y administrar trabajadores | Trabajadores | 1 |
| Registrar las raciones entregadas | Raciones | 1 |
| Registrar los menús diarios | Menú | 1 |
| Registrar los pagos realizados | Pagos + panel de Raciones | 1 |
| Registrar proveedores e insumos | Compras (insumos al vuelo; proveedores en el modelo) | 2 |
| Registrar compras de insumos | Compras | 2 |
| Apoyo a la planificación de compras | Pronóstico → insumos (con merma) | 2 |
| Consultar el historial de consumo | Raciones (navegación) + Consultas | 1 / 3 |
| Mostrar patrones históricos de consumo | Gráfico "Raciones por mes" (Dashboard) | 3 |
| Visualizar indicadores de la demanda | Tabla de indicadores (Dashboard) | 1 / 3 |
| Identificar períodos de alta y baja demanda | Segmentación por niveles (Dashboard) | 3 |

---

## Anexo — Preguntas frecuentes (repártanselas)

- **¿Dónde está exactamente el machine learning?**
  > "En dos modelos reales: el **pronóstico** (aprendizaje **supervisado**, validado
  > con backtesting) y la **segmentación con K-Means** (aprendizaje **no
  > supervisado**), más el **análisis exploratorio** que los sustenta."

- **¿Por qué no usaron un modelo más avanzado / redes neuronales?**
  > "Porque lo **medimos**: el promedio simple da ~6% de error y el SARIMAX ~16%.
  > Con estos datos, un modelo complejo **sobreajusta**. La decisión fue **basada en
  > datos**, que es lo correcto en ciencia de datos."

- **¿Qué es MAPE?**
  > "El **error porcentual absoluto medio**: en promedio, de cada 100 raciones nos
  > equivocamos en ~6."

- **¿El modelo modifica la base de datos?**
  > "No. Entrenar es **solo lectura**; los resultados se calculan al momento y se
  > muestran en el Dashboard."

- **¿Qué pasa si cambian los datos / entra un cliente nuevo?**
  > "El sistema **recalcula** los indicadores y el pronóstico automáticamente cada
  > vez que se abre el Dashboard."

- **¿Qué archivos tienen la ciencia de datos?**
  > "El paquete `ml/`: `datos.py` (serie y variables), `cluster_semanas.py` y
  > `segmentacion.py` (K-Means), `pronostico.py` (SARIMAX y la evaluación) y
  > `demanda.py` (el pronóstico de producción y la sugerencia de compras)."

---

## Checklist antes de exponer
- [ ] Abrir la app (`py app.py`) y dejarla en el **Dashboard**.
- [ ] Tener a mano: la **planilla de Raciones** con un trabajador que tenga deudas.
- [ ] Bajar hasta **"Comportamiento de la demanda"** para el gráfico de colores.
- [ ] Tener la **tabla de resultados** (MAPE) en una diapositiva de respaldo.
- [ ] Cada quien practica su transición ("…le paso la palabra a…").
