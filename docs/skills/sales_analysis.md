# Análisis de ventas

## Pasos

1. Periodo y empresa: los que indique el usuario; si no, el año en curso y la empresa por defecto. Confirma el periodo en la respuesta.
2. Mejores clientes: `aggregate_documents` sobre `Sales Invoice` con `sum` de `grand_total`, `group_by: "customer"`, `order_by: "sum_grand_total desc"` y `limit` 10, filtrando `posting_date`.
3. Productos más vendidos: `generate_report` con `Item-wise Sales Register` (`company`, `from_date`, `to_date`, `group_by: "Item"`); ordena por `amount` y suma por `item_code`.
4. Margen: `generate_report` con `Gross Profit` (`company`, `from_date`, `to_date`, `group_by: "Item Code"` o `"Customer"`). Las columnas `gross_profit` y `gross_profit_%` dan el margen; sin coste de valoración el margen sale como el 100 %, avísalo.
5. Evolución: `generate_report` con `Sales Analytics` (`tree_type`, `doc_type: "Sales Invoice"`, `value_quantity`, `range: "Monthly"`, fechas, `company`).
6. Presenta una tabla con las 10 primeras filas, el total y una frase con la conclusión.

## Cuidado

Las facturas validadas son las únicas que cuentan; los borradores y las canceladas se excluyen. Antes de un informe nuevo consulta sus filtros con `report_requirements`.
