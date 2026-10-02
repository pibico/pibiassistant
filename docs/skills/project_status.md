# Estado de un proyecto

## Pasos

1. Resuelve el proyecto con `search_documents` (`doctype: "Project"`, `purpose: "link_value"`) y léelo con `get_document` (`status`, `percent_complete`, `expected_end_date`, coste y presupuesto).
2. Tareas por estado: `aggregate_documents` sobre `Task` filtrando `project` y agrupando por `status`.
3. Tareas atrasadas: `list_documents` sobre `Task` con `exp_end_date` anterior a hoy y estado no cerrado.
4. Horas: `aggregate_documents` sobre `Timesheet` con `sum` de `total_hours` filtrando `parent_project` (los partes validados). `Timesheet Detail` es una tabla hija y no se puede agregar.
5. Coste frente a presupuesto: campos `total_costing_amount` y `estimated_costing` del proyecto.
6. Resume en un párrafo (avance, riesgos, próximos hitos) y una tabla de tareas atrasadas.
