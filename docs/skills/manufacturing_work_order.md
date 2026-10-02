# Fabricación: lista de materiales y orden de trabajo

## Pasos

1. Localiza el artículo a fabricar con `search_documents` sobre `Item` y su lista de materiales con `list_documents` sobre `BOM` (`item`, `is_active: 1`, `is_default`; `docstatus: [0, 1]`).
2. Lee la lista con `get_document` (`BOM`) para ver componentes y cantidades.
3. Comprueba existencias de cada componente con `list_documents` sobre `Bin` (`item_code`, `warehouse`, `actual_qty`) y señala los que faltan.
4. Crea la orden con `create_document` (`Work Order`): `production_item`, `bom_no`, `qty`, `wip_warehouse` y `fg_warehouse`. Revisa los campos con `get_doctype_info` si no los conoces.
5. Déjala en borrador. Valídala con `submit_document` solo si el usuario lo pide.
6. Resume: componentes con falta de stock y cantidad a fabricar.

## Cuidado

- No cambies cantidades ni listas de materiales para evitar un faltante: informa de él.
- Nunca uses `delete_document` sobre una orden validada (`docstatus` 1): se cancela desde el formulario.
