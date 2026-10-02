# Cobros pendientes y antigüedad de saldos

## Pasos

1. Total pendiente: `aggregate_documents` sobre `Sales Invoice` con `sum` de `outstanding_amount`, filtro `outstanding_amount > 0` y agrupado por `customer`.
2. Facturas vencidas: `list_documents` con `due_date < hoy` y `outstanding_amount > 0`, ordenado por `due_date`.
3. Antigüedad por tramos: informe `Accounts Receivable` o `Accounts Receivable Summary` con `generate_report` y `report_requirements` para conocer los filtros (`company`, `report_date`).
4. Presenta el resultado como tabla por cliente con tramos 0-30, 31-60, 61-90 y más de 90 días, y destaca los mayores saldos.

## Cuidado

Las facturas de venta canceladas o en borrador no cuentan. Si hay varias empresas, pregunta por cuál.
