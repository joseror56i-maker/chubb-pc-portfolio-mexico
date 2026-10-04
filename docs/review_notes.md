# Revisión de la entrega

Fecha de revisión: 2026-10-04. Se revisaron la prueba, los tres documentos y el CSV
final. No se recibió todavía el código original, el dataset crudo, las evidencias
externas ni el archivo Power BI.

## Cambios realizados

- Dataset renombrado a `data/processed/portfolio_reporting.csv`. La copia conserva
  exactamente los bytes del original. No cambiaron columnas, orden ni valores.
- Reportes alineados a `Unresolved`, que es la etiqueta realmente exportada.
- README con instrucciones ejecutables y estado real de cada entregable; eliminadas
  las instrucciones que daban por existentes notebooks y dashboard no recibidos.
- Write-up breve y apéndice completo para conservar el razonamiento original.
- Moneda marcada como supuesto MXN; corregida la referencia documental a una
  medida USD sin conversión demostrada. No se modificó ninguna medida DAX.
- Validador nuevo con rutas configurables, totales decimales exactos y pruebas.
- Separación de procesamiento, modelado, datos, reportes y visualización.

## Riesgos concretos para defender ante el evaluador

| Tema | Evidencia | Acción |
| --- | --- | --- |
| Enriquecimiento externo | El backtest reporta 0 coincidencias de 4 candidatos aceptados | Entregar la evidencia de los 52 clientes y mostrar sensibilidad dejando esos 116 registros como no resueltos |
| Identidad de clientes | 2,310 nombres exactos aparecen en varios `ClientId` | Agrupar, contar y unir por `ClientId`; el nombre solo sirve para mostrar |
| Concentración | Un cliente tiene 10,189 pólizas y 18.41% de la prima | Conservarlo en totales y mostrar su efecto en una vista de sensibilidad |
| Fechas | Inicios 2021-2024; vencimientos llegan a 2026 | Confirmar que el crecimiento use la fecha correcta y periodos comparables |
| Moneda | La prueba y el CSV no especifican moneda | Mantener el supuesto visible y revisar etiquetas y formatos del dashboard |
| Trazabilidad | El CSV no incluye industria original ni evidencia externa | Agregar dataset de auditoría o mapping antes de afirmar reproducción completa |
| Validación determinista | El leave-one-out reutiliza evidencia del mismo cliente | Explicar que valida consistencia interna; no demuestra exactitud externa de la industria |
| Intervalo de confianza | Las pólizas dentro de un cliente no son independientes | Evitar presentar el intervalo binomial por fila como garantía poblacional |

## Qué se podrá revisar cuando llegue el código

Recibir los notebooks originales como `.ipynb` o exportación `.py` de Databricks y,
si existen, módulos auxiliares y versiones de librerías. Con eso se revisarán:

- joins que multipliquen pólizas y preservación de industria original;
- rutas, parámetros, secretos y modos de escritura;
- separación entre limpieza, modelado y salida para BI;
- ajuste de transformaciones dentro de los folds y separación por cliente;
- semillas, versiones y artefactos de los experimentos;
- comentarios que expliquen decisiones no evidentes y contratos de funciones.

Los comentarios añadidos ahora corresponden al validador nuevo. Todavía no es
posible afirmar que se revisó o refactorizó el código de la solución original.
