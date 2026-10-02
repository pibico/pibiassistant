# Pedido de compra y recepción de mercancía

## Pasos

1. Identifica al proveedor con `search_documents` (`doctype: "Supplier"`, `purpose: "link_value"`). Si hay varios, pregunta cuál.
2. Revisa los campos obligatorios con `get_doctype_info` (`Purchase Order`).
3. Resuelve cada artículo con `search_documents` sobre `Item`.
4. Crea el pedido con `create_document` (`Purchase Order`): `supplier`, `schedule_date` y `items` (`item_code`, `qty`, `rate`, `schedule_date`, `warehouse`). Déjalo en borrador.
5. Valida el pedido con `submit_document` solo si el usuario lo autoriza.
6. Para la recepción, busca el pedido con `list_documents` (`status: "To Receive and Bill"` o `"To Receive"`) y créala con `create_document` (`Purchase Receipt`): `supplier`, `posting_date` e `items` con `item_code`, `qty`, `warehouse`, `purchase_order` y `purchase_order_item` (el `name` de la línea del pedido). Así se actualiza `per_received`.
7. Resume: número del documento, cantidades recibidas frente a pedidas y almacén.

## Cuidado

- Si se recibe menos de lo pedido, usa la cantidad realmente recibida; no copies la del pedido.
- No dupliques recepciones: busca antes si ya hay una `Purchase Receipt` enlazada al pedido.
