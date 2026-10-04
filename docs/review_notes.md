# Revisión del código y de la entrega

Revisión: 2026-10-04. Se leyeron los cinco exports Databricks del ZIP completo,
además de la prueba, reportes y CSV final. El ZIP no contenía el dataset original,
los resultados externos guardados ni el dashboard. Los logs de CatBoost no se
incluyeron en Git: son resultados temporales, no código ni evidencia suficiente
para reproducir los experimentos.

## Hallazgos y correcciones

| Hallazgo en el código recibido | Consecuencia | Cambio |
| --- | --- | --- |
| EDA terminaba imputando y escribiendo resultados | El análisis cambiaba artefactos de producción sin ser evidente | EDA de lectura; recuperación en etapa 02 |
| El notebook de ID no creaba `industry_filled` | El siguiente notebook dependía de una columna inexistente | Columna creada explícitamente por el módulo compartido |
| Se revisaban conflictos, pero el mapping del join no los excluía | Un cliente con dos industrias podía multiplicar pólizas | Se detiene el flujo ante conflictos; mapping único por ID |
| Rutas de tabla y Volumes del workspace estaban incrustadas | Otro equipo no podía ejecutar sin editar varias celdas | Config común y rutas resueltas desde ese archivo |
| `from pyspark.sql.functions import *` ocultaba `min`, `max`, `round` de Python | Errores al calcular máximos o redondeos escalares | Alias `F` en notebooks Spark |
| `correlation_ratio` se llamaba sin estar definida | El análisis ML podía detenerse con NameError | Función implementada y probada |
| Diagnósticos con etiquetas se hacían antes del holdout; controles reutilizaban todo el conjunto | El holdout podía influir en decisiones del experimento | Holdout reservado antes; controles restringidos a desarrollo |
| El OVR reutilizaba un escalador ajustado antes de sus folds | Información de validación entraba al preprocesamiento | Escalador ajustado dentro de cada fold |
| Colecciones Spark y nombres duplicados tenían selección/orden indeterminados | La semilla no garantizaba el mismo split o representante | Orden explícito y elección determinista |
| Backtest externo usaba regla estricta; producción aceptaba medium/secondary sin exigir grounding | El resultado del backtest no validaba la regla aplicada | Una sola regla conservadora para ambas etapas |
| Varios actions podían reevaluar `ai_enrich`; carpetas mezclaban lotes de distintos runs | Repetición de llamadas, costos y resultados antiguos | Respuestas materializadas una vez por lote; directorio nuevo y sin lectura recursiva global |
| El mapping final perdía URLs y errores del servicio | No había trazabilidad suficiente de imputación externa | Auditoría separada con fuentes y motivo de decisión |
| Cero pendientes podía causar `None + 1` al calcular lotes | Fallo si todas las industrias ya estaban resueltas | Caso vacío explícito, sin llamadas |
| Reporting escribía Parquet y mezclaba `Pending`/`Unresolved` en controles | Export CSV incompleto y conteos engañosos | CSV UTF-8 explícito, contrato y sentinel `Unresolved` |

Los comentarios añadidos explican claves de identidad, abstención, ranking de
nombres, origen de etiquetas, aislamiento del holdout y escritura de artefactos.
Los cambios de evaluación y aceptación externa son funcionales: **los resultados
históricos no deben presentarse como obtenidos con esta versión corregida**.
El CSV entregado conserva sus bytes y sus 116 imputaciones externas originales;
no fue reemplazado por una salida del flujo nuevo.

## Validación realizada y límites

- Pruebas unitarias y ejecución completa con fixture: recuperación, conservación
  de datos, conflicto de industria, duplicados, evidencia, nombres y exportación.
- Sintaxis de todos los módulos y notebooks verificada; no se ejecutaron modelos
  ni llamadas externas. Se comprobaron los valores y fingerprint del CSV entregado.
- Pendiente: correr con el dataset original, reconciliar fila por fila, revisar
  los 52 clientes externos, exportar el entorno real y ejecutar en Databricks.
- Las versiones opcionales son una propuesta fija; no equivalen al entorno original.
- Los scores CV con early stopping en el mismo fold son exploratorios. Evaluar
  generalización en el holdout separado; una mejora no prueba corrección de labels.
- El core usa el driver y se limita a 100,000 filas. El notebook ML también recoge
  features a pandas; no se presenta como solución de entrenamiento distribuido.

## Riesgos que permanecen para la entrega

| Tema | Evidencia / acción |
| --- | --- |
| Industria externa | Backtest histórico: 0 correctos / 4 aceptados. Auditar fuentes y mostrar sensibilidad con esas 116 pólizas sin imputación externa |
| Identidad | 2,310 nombres exactos en varios IDs. Unir y contar por ClientId |
| Concentración | Un cliente: 10,189 pólizas, 18.41% de prima. Mantener totales oficiales y explicar sensibilidad |
| Fechas | Inicios 2021–2024, vencimientos hasta 2026. Revisar DAX y periodos comparables |
| Moneda | MXN es un supuesto; no existe conversión USD verificada |
| LOO | Evidencia del mismo cliente no valida desempeño en clientes nuevos; las pólizas no son independientes para un intervalo binomial |
| Dashboard | Falta PBIX/PBIP. Revisar paths, datos embebidos, medidas y prueba de descarga/refresh cuando se reciba |

Las correcciones de evaluación siguen la [guía oficial de scikit-learn](https://scikit-learn.org/stable/common_pitfalls.html).
La materialización y lectura de fuentes responden al contrato documentado de
[Databricks ai_enrich](https://learn.microsoft.com/en-us/azure/databricks/sql/language-manual/functions/ai_enrich).
