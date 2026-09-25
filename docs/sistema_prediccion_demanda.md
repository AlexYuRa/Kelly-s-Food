# Sistema Predictivo y Analítico de Demanda — Kelly's Food

## Variables para Machine Learning

En consonancia con el enfoque de minería de datos y el diseño del sistema
predictivo y analítico para la empresa Kelly's Food, las variables de estudio se
seleccionaron y estructuraron a partir de los objetivos de negocio: **analizar y
predecir la demanda de raciones para optimizar el abastecimiento y controlar las
mermas**.

A nivel metodológico, y siguiendo las pautas de desarrollo de modelos de
aprendizaje automático supervisados y no supervisados, se identificaron variables
que describen el comportamiento de consumo y las condiciones del entorno
operativo. Se cuidó especialmente que **las variables usadas en el agrupamiento
sean conocidas de antemano**, evitando fugas de información (data leakage): el
régimen de una semana futura debe poder calcularse sin conocer su consumo.

> **Nota metodológica importante.** El estudio no solo *propuso* modelos, sino que
> los **evaluó empíricamente por backtesting** y seleccionó el de mejor desempeño.
> Como se detalla en la sección de resultados, los modelos complejos (SARIMAX y
> K-Means) fueron **construidos y medidos**, pero el modelo finalmente **adoptado
> en producción** fue un promedio móvil de las dos últimas semanas operativas, por
> haber obtenido el menor error de pronóstico.

### Variable de Agrupamiento (aprendizaje no supervisado)

Permite clasificar los periodos históricos para identificar regímenes de demanda
similares, y se emplea únicamente como **etiqueta interpretable**.

- **Régimen de Demanda**
  - **Indicador:** combinación de nivel de temporada y posición en el calendario
    anual (armónicos estacionales).
  - **Tipo de dato:** cualitativo categórico (3 grupos: baja / promedio / pico).
  - **Construcción:** K-Means sobre *features conocidos de antemano* (nivel de
    temporada y componentes de Fourier del calendario), **nunca sobre el consumo**.

### Variables Predictoras o Independientes

Corresponden a los factores que alimentan el modelo de series de tiempo. Todas son
**conocidas de antemano** para cualquier semana futura:

- **Estacionalidad de la temporada**
  - **Indicador:** clasificación de la temporada del periodo.
  - **Tipo de dato:** cualitativo ordinal — **tres niveles: Alta / Media / Baja
    demanda** (tabla `clasi_temporada`).
- **Calendario operativo**
  - **Indicador:** mes del año; indicador de **cierre** de fin de año (Dic–Ene, sin
    operación); indicador de **reapertura** (rampa de inicio de febrero); y
    **armónicos de Fourier** que codifican la estacionalidad anual.
  - **Tipo de dato:** cualitativo/cíclico.

> *(Se descartaron como predictores el precio de compra de insumos y la
> descripción del menú: no forman parte del modelo de demanda. El menú y los
> costos se utilizan, de forma separada, en el módulo de sugerencia de compra —
> ver sección de abastecimiento.)*

### Variable Criterio o Dependiente

- **Demanda proyectada de raciones**
  - **Indicador:** cantidad total de raciones estimadas por **semana** (agregable a
    la **quincena**, unidad de planificación).
  - **Tipo de dato:** cuantitativo discreto.

---

## Técnicas de Modelado y Resultados

La serie de trabajo es la **cantidad de raciones agregada por semana** (168 semanas,
periodo 2023-03 a 2026-06). Se optó por la granularidad semanal —en lugar de la
diaria— por ser más estable y por corresponder a la unidad real de planificación de
compras. Las semanas de cierre de fin de año se tratan como observaciones faltantes.

### 1. SARIMAX (evaluado)

Se implementó un modelo **SARIMAX** (Seasonal Autoregressive Integrated Moving
Average with eXogenous regressors) que utiliza la serie semanal de raciones como
variable dependiente e incorpora como **variables exógenas** el nivel de temporada,
el calendario (mes, cierre, reapertura, armónicos de Fourier) y, opcionalmente, la
etiqueta de régimen de demanda generada por el K-Means.

**[CAPTURA 1]** — *Salida del backtesting comparativo (`py -m ml.pronostico`),
mostrando el error MAPE de las configuraciones de SARIMAX frente a la línea base.*

### 2. K-Means (evaluado)

Se utilizó el algoritmo **K-Means** para identificar periodos de consumo similares,
agrupando **únicamente sobre features conocidas de antemano** (temporada y
calendario), sin usar el consumo, para evitar fugas de información. La etiqueta
resultante se probó como variable exógena adicional del SARIMAX, midiendo su aporte
**con y sin** ella.

### 3. Validación por backtesting (origen deslizante / walk-forward)

Cada modelo se evaluó reentrenando con el histórico disponible y pronosticando la
siguiente quincena, de forma repetida sobre los últimos periodos. Métrica: **MAPE**
(error porcentual absoluto medio). Se reporta el MAPE medio y el **MAPE mediano**
(error de una quincena *típica*), más robusto ante eventos atípicos.

**Resultados obtenidos:**

| Modelo | MAPE (quincena típica) |
|--------|------------------------|
| **Promedio móvil de 2 semanas (adoptado)** | **≈ 6 %** |
| Suavizado exponencial / Holt | ≈ 7 % |
| Repetición de la última semana (línea base) | ≈ 7 % |
| SARIMAX + temporada + calendario | ≈ 16 % |
| SARIMAX + etiqueta de clúster K-Means (1b) | ≈ 16 % (sin mejora) |

**Hallazgos:**

1. La demanda semanal es un **nivel muy persistente** (autocorrelación de 0.75) con
   saltos abruptos causados por cambios en la base de clientes, que el calendario no
   puede anticipar (correlación temporada–consumo ≈ 0.15).
2. **SARIMAX resultó menos preciso** que un promedio simple: incorpora varianza sin
   aportar señal predictiva suficiente.
3. La **etiqueta de K-Means no mejoró** la capacidad predictiva del SARIMAX; su valor
   es de interpretación, no de precisión.

### 4. Modelo adoptado en producción

Por evidencia, el sistema utiliza el **promedio de las dos últimas semanas
operativas**, con una banda de compra (± una desviación de las semanas recientes).
Es el de menor error (~6 % en una quincena típica) y el más simple de operar.

**[CAPTURA 2]** — *Panel de pronóstico del Dashboard: estimación de raciones para la
próxima quincena con su banda (evidencia del modelo en funcionamiento en la app).*

---

## Componente de Abastecimiento (traducción demanda → insumos)

A partir de las raciones proyectadas, el sistema estima las **cantidades de insumos
a comprar**, multiplicando la demanda por el consumo típico por ración de cada
insumo (derivado de las recetas recientes e **incluyendo la merma**).

> *Limitación de datos:* el costo monetario solo está disponible para 6 de 30
> insumos, por lo que la sugerencia se ordena por **cantidad** y no por costo.

**[CAPTURA 3]** — *Panel del Dashboard con los "Insumos a comprar (aprox.)": chips
por insumo con su cantidad (kg, litros, etc.) para la próxima quincena.*

**[CAPTURA 4]** *(opcional)* — *Salida de consola `py -m ml.demanda`, mostrando el
pronóstico de la quincena y la lista de insumos con sus cantidades.*

---

## Resumen

| Aspecto | Estado |
|---------|--------|
| Serie de demanda (raciones/semana) | Implementada |
| Exógenas: temporada + calendario (Fourier, cierre, reapertura) | Implementadas |
| SARIMAX | Evaluado — descartado por menor precisión |
| K-Means (régimen de semana, anti-fuga) | Evaluado — sin aporte predictivo |
| **Promedio móvil de 2 semanas** | **Adoptado (producción)** |
| Sugerencia de compra de insumos (con merma) | Implementada |
