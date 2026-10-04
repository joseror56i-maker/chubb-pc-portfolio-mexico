# Revisión del dashboard

Evidencia local del proyecto y los CSV; revisión del 2026-10-04. El proyecto tiene
dos páginas, 12 tablas, 70 medidas y 165 contenedores visuales, incluyendo formas,
texto y grupos. Los recursos registrados y las referencias del reporte existen.

## Preparación realizada

- Nombre público: `dashboard/premium_growth.pbip`, con carpetas `.Report` y
  `.SemanticModel` del mismo nombre y enlaces relativos actualizados.
- La consulta usa el parámetro requerido `ReportingCsvPath`. El helper genera una
  copia local configurada según donde se descargó el repositorio; el proyecto
  compartido no conserva rutas personales.
- Tema registrado con un nombre breve y recursos gráficos incluidos.
- Exclusión de `cache.abf`, `localSettings.json`, queries pendientes, respaldos
  y archivos de referencia que no utiliza el reporte.
- No se cambiaron las fórmulas DAX, las páginas ni las prioridades de ranking.
- Se verificó la definición TMDL usando el deserializador oficial Microsoft TOM
  19.114.12: 12 tablas, 70 medidas y el parámetro reconocidos correctamente.

## Riesgos de descarga y de uso

| Riesgo | Efecto | Forma de manejarlo |
| --- | --- | --- |
| Descargar solo el PBIP | Faltan reporte, modelo, imágenes y datos | Descargar/clonar el repositorio completo y conservar estructura |
| CSV en una ubicación distinta | Refresh no encuentra el archivo | Ejecutar setup o configurar ReportingCsvPath en Desktop |
| Caché omitida | Visuales sin datos hasta la primera actualización | Refresh tras configurar el CSV; no publicar una caché personal |
| Versión Desktop incompatible / paths extensos | Proyecto no abre o no reconoce el formato | Desktop reciente y ruta corta en Windows |
| Calendario fijo 2020–2024 | Policies posteriores quedarían fuera de la dimensión de fechas | Extender calendario cuando cambie el periodo del dataset |
| Comparar YTD contra total histórico | Reconciliación aparentemente incorrecta | Usar mismo corte y filtros; controles por año disponibles |
| Crecimiento sin base LY | Tasa indefinida | Mantener blank/Sin base LY, como indica el modelo |
| Filtro de cliente dominante basado en ID explícito | Una nueva cartera puede tener otra concentración | Revisar criterio al sustituir el dataset |
| Datos o selecciones guardados en PBIR | El proyecto puede revelar valores de filtros | Revisión local de metadata y publicación bajo el alcance autorizado |

La fecha de negocio está ligada a `policy_start_date`; el fin de póliza no dirige
el calendario. El cutoff está separado de la tabla de fechas y las medidas YTD
usan su fecha máxima. La dimensión de clientes y las etiquetas ID+nombre evitan
confundir empresas con nombres iguales. El selector de concentración conserva
una opción de cartera total y opciones de sensibilidad.

Se conservaron las 1,356 pólizas `Unresolved` del dataset final. Los campos
`fill_method` y `confidence_level` permiten identificar la parte externa de la
solución. Los importes se presentan en unidades de origen; MXN sigue siendo un
supuesto, no una conversión confirmada.

## Verificación pendiente en Power BI Desktop

La sintaxis TMDL, referencias y datos se verificaron localmente. La librería de
metadata no calcula DAX, no carga el motor de refresh ni renderiza visuales.
Abrir la copia preparada, actualizar, revisar año 2024 y Last Year contra los
controles CSV, probar filtros entre páginas y alternar los dos bookmarks de detalle.
Guardar/exportar PBIX o capturar una preview solamente desde ese reporte real.

Las [referencias de proyecto](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-report)
y el comportamiento de [modelos sin caché](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-dataset)
están documentados por Microsoft.
