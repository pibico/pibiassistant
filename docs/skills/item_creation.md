# Alta de artículo

## Pasos

1. Busca antes de crear: `search_documents` sobre `Item` por código y por nombre. Si lista con `list_documents`, pasa `docstatus: [0, 1]` y revisa también los deshabilitados (`disabled`).
2. Consulta `get_doctype_info` (`Item`) para conocer los campos obligatorios de este sitio (grupo de artículos, unidad de medida).
3. Resuelve `item_group` y `stock_uom` con `search_documents` (`purpose: "link_value"`).
4. Crea el artículo con `create_document`: `item_code`, `item_name`, `item_group`, `stock_uom`, `is_stock_item` y `description`.
5. Si el usuario da precio, crea un `Item Price` con `price_list`, `item_code` y `price_list_rate`.
6. Confirma el nombre del documento creado.

## Cuidado

- No inventes códigos ni unidades: si faltan datos, pregunta.
- No modifiques un artículo existente sin que el usuario lo pida.
