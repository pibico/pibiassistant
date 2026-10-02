# Registrar un cobro o un pago

## Pasos

1. Pregunta si es un cobro de cliente (`payment_type: "Receive"`, `party_type: "Customer"`) o un pago a proveedor (`payment_type: "Pay"`, `party_type: "Supplier"`).
2. Localiza la factura pendiente con `list_documents` sobre `Sales Invoice` o `Purchase Invoice` con `outstanding_amount > 0` y comprueba el saldo con `get_document`.
3. Comprueba que no exista ya un `Payment Entry` para esa factura con `list_documents` pasando `docstatus: [0, 1]` (los borradores no salen por defecto). Revisa los campos con `get_doctype_info` (`Payment Entry`) y la forma de pago con `search_documents` sobre `Mode of Payment`.
4. Crea el documento con `create_document` (`Payment Entry`): `payment_type`, `party_type`, `party`, `posting_date`, `mode_of_payment`, `paid_amount`, `received_amount`, `paid_from`, `paid_to`, `reference_no` y `reference_date`.
5. Enlaza la factura en `references`: `reference_doctype`, `reference_name` y `allocated_amount`.
6. Déjalo en borrador. Valídalo con `submit_document` solo si el usuario lo pide expresamente.
7. Resume: importe, factura saldada o saldo restante.

## Cuidado

- `allocated_amount` no puede superar el saldo pendiente de la factura.
- Las cuentas `paid_from` y `paid_to` dependen del tipo de pago y de la forma de pago; si no se resuelven solas, pregunta antes de inventarlas.
- Nunca uses `delete_document` sobre un pago validado (`docstatus` 1): se cancela desde el formulario.
- Confirma importe y tercero antes de validar: un pago validado solo se corrige cancelándolo.
