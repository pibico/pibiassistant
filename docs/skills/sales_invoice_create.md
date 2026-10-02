# Crear una factura de venta

## Pasos

1. Identifica al cliente con `search_documents` (`doctype: "Customer"`, `purpose: "link_value"`). Si hay varios, pregunta cuál.
2. Revisa los campos obligatorios con `get_doctype_info` (`Sales Invoice`).
3. Resuelve cada artículo con `search_documents` sobre `Item` y toma precio y unidad de la lista de precios si el usuario no da tarifa.
4. Crea la factura con `create_document`: `customer`, `posting_date`, `due_date` y `items` (`item_code`, `qty`, `rate`). Si es un pedido o albarán existente, indica el origen en las líneas.
5. Comprueba que se aplicaron los impuestos (IVA) de la plantilla del cliente y que el total coincide con lo esperado. Si hay retención de IRPF, recargo de equivalencia, operación intracomunitaria o inversión del sujeto pasivo, sigue la guía `spanish-tax-lines-es` (get_skill).
6. Deja la factura en borrador. Valídala con `submit_document` solo si el usuario lo pide de forma explícita; una factura validada no se edita.

## Cuidado

Confirma con el usuario importes y cliente antes de validar. Para corregir una factura validada hay que cancelarla o emitir una nota de crédito.
