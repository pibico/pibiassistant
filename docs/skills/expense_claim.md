# Gastos de empleado

## Pasos

1. Identifica al empleado con `search_documents` (`doctype: "Employee"`, `purpose: "link_value"`). Si el usuario habla de sí mismo, busca su ficha por su usuario.
2. Revisa los campos con `get_doctype_info` (`Expense Claim`) y los tipos de gasto con `list_documents` sobre `Expense Claim Type`.
3. Si el usuario adjunta tickets, léelos con `extract_file_content` para obtener fecha e importe.
4. Crea la solicitud con `create_document` (`Expense Claim`): `employee`, `posting_date` y `expenses` con `expense_date`, `expense_type`, `amount` y `description`.
5. Adjunta cada justificante con `attach_file` al documento creado.
6. Déjala en borrador. Valídala con `submit_document` solo si el usuario lo pide.
7. Resume: total reclamado (`total_claimed_amount`), líneas y estado de aprobación (`approval_status`).

## Cuidado

- No inventes importes ni fechas: si un ticket es ilegible, pregunta.
- La aprobación (`expense_approver`) la decide la persona responsable; no la cambies por tu cuenta.
