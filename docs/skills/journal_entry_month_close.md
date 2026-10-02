# Asiento contable y cierre de mes

## Pasos

1. Para un asiento manual, revisa los campos con `get_doctype_info` (`Journal Entry`) y resuelve cada cuenta con `search_documents` sobre `Account` (`purpose: "link_value"`).
2. Crea el asiento con `create_document` (`Journal Entry`): `posting_date`, `voucher_type` y `accounts` con `account`, `debit_in_account_currency` y `credit_in_account_currency`. El total del debe ha de igualar al del haber.
3. Déjalo en borrador. Valídalo con `submit_document` solo si el usuario lo pide.
4. Para revisar el cierre del mes, comprueba con `list_documents` y `docstatus: 0` los borradores pendientes de `Sales Invoice`, `Purchase Invoice`, `Payment Entry` y `Journal Entry` con `posting_date` dentro del mes.
5. Genera el balance de sumas y saldos con `generate_report` (`Trial Balance`) para el mes y comprueba que debe y haber coinciden.
6. Resume: borradores pendientes, descuadres y los asientos propuestos.

## Cuidado

- No inventes cuentas ni importes; si una cuenta no existe en el plan contable, pregunta.
- No valides asientos en periodos cerrados: informa del error.
- Nunca uses `delete_document` sobre un documento validado (`docstatus` 1): se cancela desde el formulario.
