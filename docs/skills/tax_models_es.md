# Preparación de modelos 303, 347 y 349

Es una ayuda a la preparación, no una presentación: el asesor debe revisar las cifras antes de presentar nada. Usa solo herramientas de lectura.

## Modelo 303 (IVA trimestral)

Sigue la guía de resumen de IVA (`vat-summary-es`): `generate_report` con `Sales Register` y `Purchase Register` del trimestre.

## Modelo 347 (operaciones con terceros)

1. Ejercicio natural completo y empresa confirmada.
2. Clientes: `aggregate_documents` sobre `Sales Invoice` (`docstatus: 1`, `posting_date` dentro del año), agrupado por `customer`, con `sum` de `grand_total`.
3. Proveedores: lo mismo sobre `Purchase Invoice` agrupado por `supplier`.
4. Conserva solo los terceros cuyo total anual supera 3.005,06 EUR (IVA incluido) y reparte el importe por trimestre si el usuario lo pide, repitiendo la consulta por trimestre.
5. Añade el NIF de cada tercero con `get_document` (`tax_id`). Señala los que no lo tienen.

## Modelo 349 (operaciones intracomunitarias)

1. Facturas del periodo de terceros con NIF-IVA de la UE: `list_documents` sobre `Sales Invoice` y `Purchase Invoice` con `docstatus: 1`, filtrando por el país del tercero o por `tax_id` con prefijo de país de la UE.
2. Suma por tercero con `aggregate_documents` y separa entregas de adquisiciones.
3. Indica la clave de operación solo si el usuario la facilita; no la deduzcas.

## Cuidado

- Excluye borradores y documentos cancelados.
- Menciona el umbral y el periodo usados, y la fecha de la consulta.
- Si el usuario pide presentar o generar el fichero oficial, explica que se hace en la sede electrónica o con su asesor.
