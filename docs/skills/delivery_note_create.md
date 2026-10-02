# Albarán de entrega

## Pasos

1. Localiza el pedido de venta con `search_documents` (`doctype: "Sales Order"`) o `list_documents` filtrando por cliente y `status: "To Deliver and Bill"` o `"To Deliver"`.
2. Léelo con `get_document` y confirma con el usuario qué líneas y cantidades se entregan.
3. Comprueba existencias con `list_documents` sobre `Bin` (`item_code`, `warehouse`, `actual_qty`) antes de entregar.
4. Crea el albarán con `create_document` (`Delivery Note`): `customer`, `posting_date` e `items` con `item_code`, `qty`, `warehouse`, `against_sales_order` y `so_detail` (el `name` de la línea del pedido).
5. Antes de crear, comprueba con `list_documents` sobre `Delivery Note` (`against_sales_order`) pasando `docstatus: [0, 1]` que no exista ya un albarán, borrador incluido. Déjalo en borrador. Valídalo con `submit_document` solo si el usuario lo pide: al validarlo se descuenta el stock.
6. Resume: número del albarán, líneas entregadas y pendientes del pedido.

## Cuidado

- Nunca uses `delete_document` sobre un albarán validado (`docstatus` 1): se cancela desde el formulario.
- Sin stock suficiente la validación fallará; informa de la diferencia en lugar de modificar cantidades por tu cuenta.
- Para facturar lo entregado, usa la skill sales-invoice-create indicando el albarán como origen.
