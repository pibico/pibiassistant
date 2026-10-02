# Conciliación bancaria

## Pasos

1. Lista los movimientos pendientes con `list_documents` sobre `Bank Transaction` (`status: "Unreconciled"`; campos `date`, `deposit`, `withdrawal`, `description`, `bank_account`, `unallocated_amount`).
2. Para cada movimiento busca candidatos con `list_documents` sobre `Payment Entry` (`docstatus: [0, 1]`, mismo importe y fecha cercana) y, si no hay pago, sobre `Sales Invoice` o `Purchase Invoice` con `outstanding_amount` igual al importe.
3. Presenta una tabla: movimiento, candidato propuesto y grado de coincidencia (importe exacto, referencia, tercero).
4. Si el usuario confirma un cobro o pago que aún no existe, sigue la skill payment-entry y deja el documento en borrador.
5. La asignación final del movimiento al documento se hace en la herramienta de conciliación bancaria del formulario; indica el enlace al `Bank Transaction`.

## Cuidado

- No concilies por tu cuenta ni modifiques importes para que cuadren.
- Si hay varios candidatos con el mismo importe, pregunta cuál corresponde.
- Nunca uses `delete_document` sobre un documento validado (`docstatus` 1): se cancela desde el formulario.
