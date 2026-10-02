# Consulta de stock

## Pasos

1. Existencias por artículo y almacén: `aggregate_documents` sobre `Bin` con `sum` de `actual_qty`, agrupando por `item_code` o `warehouse`; filtra por `item_code` si el usuario nombra un artículo (resuélvelo antes con `search_documents`).
2. Valor del inventario: `sum` de `stock_value` sobre `Bin`.
3. Artículos bajo mínimo: `list_documents` sobre `Bin` con `actual_qty` y `item_code`; compara con `safety_stock` de `Item` o con las reglas de reposición (`Reorder Level`).
4. Movimientos de un artículo: `list_documents` sobre `Stock Ledger Entry` ordenado por `posting_date desc`.
5. Para un informe estándar usa `generate_report` con `Stock Balance`.

## Cuidado

Los almacenes tipo grupo no tienen existencias propias; consulta sus hijos. Indica la fecha de la consulta en la respuesta.
