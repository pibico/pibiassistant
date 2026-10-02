# Factura rectificativa o abono

## Pasos

1. Localiza la factura original con `search_documents` o `list_documents` (`Sales Invoice` para ventas, `Purchase Invoice` para compras) y léela con `get_document`.
2. Confirma que está validada (`docstatus: 1`) y pregunta el motivo y si el abono es total o de líneas concretas.
3. Crea el abono con `create_document` en el mismo doctype: `is_return: 1`, `return_against` con el número de la factura original, el mismo cliente o proveedor y `items` con `item_code` y `qty` en negativo (y `rate` igual al original).
4. Déjalo en borrador y comprueba que el total es el importe negativo esperado, con los mismos impuestos que el original. Si el original tenía retención de IRPF, recargo de equivalencia o inversión del sujeto pasivo, revisa la guía `spanish-tax-lines-es` (get_skill) para que el abono los revierta igual.
5. Valídalo con `submit_document` solo si el usuario lo pide. Al validarlo reduce el saldo pendiente de la factura original.
6. Resume: número del abono, importe y saldo resultante de la factura original.

## Cuidado

- Un abono no puede superar lo facturado en la original.
- Si la factura original ya se cobró, el abono genera un saldo a favor; avisa al usuario en lugar de registrar el reembolso por tu cuenta.
- No canceles la factura original salvo petición expresa: la cancelación y el abono tienen efectos distintos.
