# De presupuesto a pedido de venta

## Pasos

1. Localiza el presupuesto con `search_documents` (`doctype: "Quotation"`) o `list_documents` filtrando por cliente y estado.
2. Léelo con `get_document` y confirma con el usuario que está aprobado y vigente (`valid_till`).
3. Si el presupuesto está en borrador, valídalo con `submit_document` (solo si el usuario lo autoriza).
4. Crea el pedido con `create_document` (`Sales Order`): `customer`, `delivery_date` y las líneas del presupuesto (`item_code`, `qty`, `rate`, referencia a `prevdoc_docname`).
5. Resume: número del pedido, importes y fecha de entrega. Deja el pedido en borrador salvo orden expresa.

## Cuidado

- Un presupuesto caducado o perdido (`status: "Lost"`) no debe convertirse sin preguntar.
- No dupliques pedidos: busca antes con `list_documents` sobre `Sales Order` pasando `docstatus: [0, 1]` (por defecto solo salen los validados y se perderían los borradores) si ya hay uno enlazado al presupuesto; `get_linked_documents` sobre el presupuesto lista también los documentos enlazados.
- Nunca uses `delete_document` sobre un documento validado (`docstatus` 1): se cancela desde el formulario.
