# Gestión de tareas

## Pasos

1. Pendientes: `list_documents` sobre `Task` con `status` distinto de `Completed` y `Cancelled` (campos `subject`, `status`, `priority`, `exp_end_date`, `project`), filtrando por `project` si el usuario lo indica.
2. Atrasadas: las que tienen `exp_end_date` anterior a hoy. Carga por estado con `aggregate_documents` sobre `Task` agrupando por `status`.
3. Crea una tarea con `create_document` (`Task`): `subject`, `project`, `priority`, `exp_start_date`, `exp_end_date` y `description`. Resuelve el proyecto con `search_documents`.
4. Para asignar a una persona, crea una `ToDo` con `create_document`: `allocated_to`, `reference_type: "Task"`, `reference_name` y `description`.
5. Para cambiar el estado, usa `update_document` sobre `Task` con solo el campo `status`.
6. Resume lo creado o modificado con los nombres de documento.

## Cuidado

- No marques como completada una tarea sin confirmación del usuario.
- Resuelve la persona por usuario con `search_documents` en lugar de adivinar el correo.
