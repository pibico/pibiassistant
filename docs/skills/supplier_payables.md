# Pagos pendientes a proveedores

## Pasos

1. Total pendiente: `aggregate_documents` sobre `Purchase Invoice` con `sum` de `outstanding_amount`, filtro `outstanding_amount > 0` y `docstatus: 1`, agrupado por `supplier`.
2. Facturas vencidas: `list_documents` con `due_date < hoy` y `outstanding_amount > 0`, ordenado por `due_date`, con `supplier`, `bill_no`, `due_date` y `outstanding_amount`.
3. Próximos vencimientos: las mismas facturas con `due_date` en los siguientes 30 días.
4. Antigüedad por tramos: informe `Accounts Payable` o `Accounts Payable Summary` con `generate_report` y `report_requirements` para conocer los filtros (`company`, `report_date`).
5. Presenta tabla por proveedor, separando vencido y por vencer, y destaca los mayores saldos y las facturas con más retraso.

## Cuidado

Las facturas de compra en borrador o canceladas no cuentan. Los abonos (`is_return`) restan del saldo. Si hay varias empresas, pregunta por cuál.
