# Impuestos especiales en facturas (España)

## Cuándo usarla

Al crear o revisar una factura de venta o compra cuyo PDF o enunciado incluya retención de IRPF, recargo de equivalencia, una operación con la UE o una inversión del sujeto pasivo. Si solo hay IVA normal, no hace falta.

## Cómo detectar cada caso

1. **Retención IRPF** (profesionales y alquileres): líneas o texto con "retención", "IRPF" o un porcentaje negativo (15 %, 7 %, 19 %). Resta de la base; el total a pagar es base + IVA - retención.
2. **Recargo de equivalencia** (comercio minorista): cuotas adicionales de 5,2 %, 1,4 % o 0,5 % sobre la base, junto al IVA de 21 %, 10 % o 4 %.
3. **Entrega o adquisición intracomunitaria**: proveedor o cliente con NIF-IVA de otro país de la UE y factura sin IVA. Anota el NIF-IVA en la factura.
4. **Inversión del sujeto pasivo** (construcción, chatarra, etc.): la factura dice "inversión del sujeto pasivo" y no lleva IVA; el IVA lo autorrepercute el receptor.

## Pasos

1. Extrae el documento con `extract_file_content` y anota base, tipos, retenciones y total impreso.
2. Consulta las plantillas de impuestos y las cuentas disponibles con `search_documents` (`Sales Taxes and Charges Template` o `Purchase Taxes and Charges Template`) y `get_doctype_info` sobre la factura.
3. Elige la plantilla que coincida con el caso. Si ninguna encaja, no inventes cuentas: indica al usuario qué plantilla falta.
4. Crea la factura en borrador con `create_document`. Una retención va como línea de impuesto con importe negativo y `add_deduct_tax: Deduct` sobre el total neto.
5. Relee la factura con `get_document` y compara `grand_total` con el total del PDF. Si la diferencia es de más de 0,01 EUR, revisa tipos y redondeos antes de seguir; no ajustes importes a mano para cuadrar.
6. Resume: base, cada impuesto y retención, total y cualquier diferencia que quede.

## Cuidado

- No valides con `submit_document` salvo petición expresa.
- Estas operaciones afectan a modelos fiscales (303, 111, 115, 349): indica que debe revisarlas el asesor.
- Para rectificar una factura ya validada usa la guía de factura rectificativa (`credit-note-es`).
