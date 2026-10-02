# Cómo usar get_pending_approvals

Devuelve los documentos que esperan la aprobación del usuario actual según el sistema de Workflow Action. No consulta ToDo ni notificaciones.

## Parámetros

- `doctype` (opcional): limita a un tipo de documento.
- `limit` (opcional, máximo 200).
- `include_actions` (opcional): incluye las acciones de workflow disponibles.

## Pasos

1. Llama sin `doctype` para ver todo lo pendiente.
2. Para decidir sobre un documento, ábrelo con `get_document` y ejecuta la acción con `run_workflow`.
3. No apruebes en nombre del usuario sin que lo haya pedido de forma explícita.
