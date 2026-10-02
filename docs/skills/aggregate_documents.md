# Cómo usar aggregate_documents

## Cuándo usarla

Para totales sin traer filas: contar, sumar, promediar o sacar mínimo y máximo, con o sin agrupación. Es preferible a `list_documents` para cualquier total.

## Parámetros

| Parámetro | Descripción |
|-----------|-------------|
| `doctype` | DocType (obligatorio) |
| `aggregates` | Lista de `{function, field}`; `function` es `count`, `sum`, `avg`, `min` o `max`. Por defecto un `count` |
| `group_by` | Un campo por el que agrupar |
| `filters` | Filtros como en `list_documents` |
| `order_by`, `limit` | Orden y número de grupos |

## Ejemplos

Facturas de venta por cliente: `{"doctype": "Sales Invoice", "aggregates": [{"function": "sum", "field": "grand_total"}], "group_by": "customer", "filters": {"posting_date": [">=", "2026-01-01"]}}`

Tareas por estado: `{"doctype": "ToDo", "group_by": "status"}`

## Notas

- En DocTypes que se validan (facturas, pedidos) se aplica `docstatus: 1` salvo que indiques otra cosa.
- Si necesitas campos de cada documento, usa `list_documents`.
