# Revisión del dashboard

## Entrega utilizable y comprobación real

`dashboard/premium_growth.pbix` fue guardado desde Power BI Desktop después de
cargar el modelo. Se abrió una copia en otra carpeta que contenía sólo el PBIX,
se actualizó y se comprobaron Overview y Detalle. La consulta incorpora el CSV
comprimido en el modelo; no usa File.Contents, rutas personales ni credenciales.

Las consultas DAX del modelo reabierto reconciliaron 50,441 pólizas, 8,565 clientes,
1,356 Unresolved y primas de 23,465,362,773.10. Los totales, crecimiento y tasas
anuales 2021–2024 coinciden con los controles CSV independientes. Evidencia en
[dashboard_runtime_validation.json](../reports/dashboard_runtime_validation.json).

El modelo tiene 12 tablas y 70 medidas. Se conservaron fórmulas DAX, páginas,
ranking, recursos gráficos y selecciones del reporte. El CSV final no cambió.
Los controles estáticos y la deserialización Microsoft TOM permanecen disponibles
en dashboard_validation.json; esa evidencia se distingue de las pruebas del PBIX.

## Uso y riesgos restantes

| Situación | Efecto y manejo |
| --- | --- |
| Abrir el PBIX entregable | Los datos ya están cargados; no se requiere el CSV |
| Mover o actualizar el PBIX | Refresh usa la instantánea integrada; no depende de una carpeta externa |
| Incorporar datos nuevos | Generar proyecto con build_standalone.py, revisar fechas/datos, cargar y exportar de nuevo en Desktop |
| Editar el PBIP de desarrollo | Mantener Report/SemanticModel juntos y configurar ReportingCsvPath mediante setup_dashboard.py |
| Comparar tarjetas con total histórico | Aplicar el mismo año/corte y filtros; los YTD no son totales de cuatro años |
| Selecciones guardadas | Corte diciembre 2023 y sensibilidad sin cliente dominante; elegir Total portfolio para cifras oficiales |
| Calendario y concentración | Revisar cobertura temporal y cliente explícito cuando cambie la cartera |
| LY ausente/cero | Mantener blank/Sin base LY; no forzar porcentajes |
| Distribuir PBIX | Incluye los datos completos; mismo alcance autorizado que el CSV |

La fecha de negocio es policy_start_date. MXN sigue siendo un supuesto;
no se afirma conversión a USD. ClientId define identidad y las etiquetas combinan
ID+nombre. Las pólizas Unresolved y la procedencia externa permanecen visibles.

La apertura, actualización y reconciliación DAX ya se comprobaron. La aceptación
completa de legibilidad, filtros múltiples, bookmarks y claridad para negocio
queda a cargo del candidato. No se publicó en Power BI Service.

Referencias: [proyectos y Save as nativo](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-overview),
[Binary.Decompress](https://learn.microsoft.com/en-us/powerquery-m/binary-decompress).
