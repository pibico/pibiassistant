# Alta de cliente o proveedor por NIF

## Pasos

1. Busca antes de crear: `search_documents` en `Customer` o `Supplier` por NIF/CIF (campo `tax_id`) y por nombre. Si existe, úsalo. Si compruebas con `list_documents`, pasa `docstatus: [0, 1]` para no perder registros en borrador.
2. Consulta `get_doctype_info` para saber qué campos son obligatorios en este sitio (grupo, territorio, tipo).
3. Crea con `create_document`: nombre fiscal, `tax_id` (NIF/CIF en mayúsculas, sin espacios ni guiones), `customer_type` o `supplier_type` (`Company` o `Individual`) y país.
4. Si el usuario da dirección y contacto, crea `Address` y `Contact` enlazados al tercero.
5. Confirma el resultado con el nombre del documento creado.

## Cuidado

- Formato NIF: 8 cifras y letra, o letra y 7 cifras y control para CIF; no inventes la letra de control.
- No modifiques un tercero existente sin que el usuario lo pida.
- Nunca uses `delete_document` sobre un documento validado (`docstatus` 1): se cancela desde el formulario.
