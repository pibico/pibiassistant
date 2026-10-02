# Resumen de IVA (España)

## Pasos

1. Periodo: trimestre o mes que indique el usuario; si no lo dice, el trimestre natural anterior. Confirma la empresa.
2. IVA repercutido: `generate_report` con `Sales Register` (`company`, `from_date`, `to_date`, `include_payments: 0`). Las columnas `net_total`, `tax_total` y `grand_total` dan base, cuota y total; hay además una columna por cuenta de impuesto. Para el desglose por tipo (21 %, 10 %, 4 %) usa `Item-wise Sales Register` con las mismas fechas: trae el tipo y el importe de cada impuesto por línea.
3. IVA soportado: lo mismo con `Purchase Register`. No intentes agregar `Sales Taxes and Charges` o `Purchase Taxes and Charges` con `aggregate_documents`: son tablas hijas y la herramienta las rechaza.
4. Para un total rápido sin filas, `aggregate_documents` sobre `Sales Invoice` / `Purchase Invoice` con `sum` de `net_total` y `total_taxes_and_charges`.
5. Resultado: repercutido menos soportado, con desglose por tipo y bases imponibles.

## Cuidado

Es una ayuda a la preparación del modelo 303, no una presentación: indica que debe revisarlo el asesor. Excluye documentos cancelados y borradores.
