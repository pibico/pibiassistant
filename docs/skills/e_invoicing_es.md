# Facturación electrónica (España)

## Pasos

1. Revisa con `get_doctype_info` (`Sales Invoice`) qué campos de facturación electrónica existen en este sitio (por ejemplo identificador, código QR o estado de envío). No asumas ninguno: usa solo los que aparezcan.
2. Comprueba los datos del cliente con `get_document` (`Customer`): `tax_id` (NIF/CIF) y dirección completa. Si faltan, sigue la skill party-by-nif.
3. Comprueba en la factura: serie y numeración correlativa, `posting_date`, líneas con tipo de IVA y totales; para una rectificativa sigue la skill credit-note-es.
4. Lista con `list_documents` y `docstatus: [0, 1]` las facturas del periodo para detectar saltos de numeración o borradores sin emitir.
5. Resume: facturas listas, incidencias de datos y qué falta antes de validarlas.

## Cuidado

- No inventes identificadores, huellas ni códigos QR: los genera la integración instalada al validar.
- Una factura validada no se modifica ni se borra: se rectifica con una nota de crédito.
- Si no hay integración instalada, indícalo y limítate a revisar los datos.
