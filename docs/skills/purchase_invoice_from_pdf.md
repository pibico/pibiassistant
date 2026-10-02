# Factura de compra a partir de un PDF

## Objetivo

Crear una Purchase Invoice a partir de una factura de proveedor en PDF o imagen que el usuario ha subido al chat.

## Pasos

1. Extrae el contenido con `extract_file_content` (`operation: "extract"`, o `"ocr"` si es una imagen o un escaneo; `"extract_tables"` si las líneas están en tabla).
2. Localiza el proveedor con `search_documents` (`doctype: "Supplier"`, `purpose: "link_value"`), buscando primero por NIF/CIF y después por nombre. Si no existe, sigue la guía de alta de terceros por NIF.
3. Consulta los campos obligatorios con `get_doctype_info` (`Purchase Invoice`).
4. Crea la factura con `create_document`: `supplier`, `bill_no` (número de factura del proveedor), `bill_date`, `posting_date`, moneda y líneas (`items` con `item_code` o descripción, `qty`, `rate`). Resuelve cada artículo con `search_documents`.
5. Comprueba los impuestos: IVA soportado con la plantilla de impuestos de compra del proveedor. Compara el total calculado con el del PDF. Si el PDF lleva retención de IRPF, recargo de equivalencia, operación intracomunitaria o inversión del sujeto pasivo, sigue la guía `spanish-tax-lines-es` (get_skill).
6. Adjunta el PDF original con `attach_file` usando el `file_url` del chat y el `name` de la factura.
7. Deja la factura en borrador y resume al usuario: proveedor, número, fecha, base, IVA y total. No la valides (`submit_document`) salvo que lo pida.

## Cuidado

- Antes de crear, comprueba duplicados con `list_documents` sobre `Purchase Invoice` (`supplier`, `bill_no`) pasando `docstatus: [0, 1]`: por defecto solo se devuelven las validadas y se te escaparían los borradores. Si ya existe, avisa en lugar de duplicar.
- Nunca uses `delete_document` sobre un documento validado (`docstatus` 1): se cancela desde el formulario.
- Si algún dato no se lee con claridad, pregunta antes de crear.
