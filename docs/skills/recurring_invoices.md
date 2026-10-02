# Facturas recurrentes

## Pasos

1. Localiza la factura de origen con `search_documents` o `list_documents` sobre `Sales Invoice` y léela con `get_document`.
2. Comprueba si ya está programada con `list_documents` sobre `Auto Repeat` (`reference_doctype`, `reference_document`, `status`, `frequency`, `next_schedule_date`).
3. Revisa los campos con `get_doctype_info` (`Auto Repeat`).
4. Crea la repetición con `create_document` (`Auto Repeat`): `reference_doctype`, `reference_document`, `frequency` (por ejemplo `Monthly`), `start_date`, `end_date` y `submit_on_creation: 0`.
5. Resume: frecuencia, próxima fecha y si se crean en borrador.

## Cuidado

- Por defecto las facturas generadas se dejan en borrador; no actives la validación automática sin petición expresa.
- No programes dos repeticiones para el mismo documento: comprueba antes con `list_documents`.
- Nunca uses `delete_document` sobre un documento validado (`docstatus` 1): se cancela desde el formulario.
