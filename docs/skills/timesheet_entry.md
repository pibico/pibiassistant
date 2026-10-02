# Partes de horas

## Pasos

1. Pregunta (o deduce del contexto) empleado, proyecto o tarea, fecha, horas y descripción.
2. Resuelve el proyecto y la tarea con `search_documents` (`Project`, `Task`, `purpose: "link_value"`).
3. Mira los campos con `get_doctype_info` (`Timesheet`). Busca un parte abierto del mismo empleado y periodo con `list_documents` para añadir líneas en vez de duplicar.
4. Crea o actualiza con `create_document` / `update_document`: cada línea lleva `activity_type`, `from_time` o `hours`, `project`, `task`.
5. Valida con `submit_document` solo si el usuario lo pide.

## Resumen de horas

Para totales usa `aggregate_documents` sobre `Timesheet` con `sum` de `total_hours` agrupando por `employee` o `parent_project`. `Timesheet Detail` es una tabla hija y la herramienta no la agrega.
