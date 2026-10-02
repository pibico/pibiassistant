# Seguimiento de incidencias

## Pasos

1. Lista las abiertas con `list_documents` sobre `Issue` (`status: "Open"`; campos `name`, `subject`, `customer`, `priority`, `opening_date`, `raised_by`), ordenadas por `opening_date`.
2. Resumen por prioridad o estado con `aggregate_documents` sobre `Issue` agrupando por `priority` o `status`.
3. Lee una incidencia con `get_document` para ver su descripción y su historial.
4. Si el usuario quiere cambiar el estado o la prioridad, usa `update_document` sobre `Issue` con solo esos campos.
5. Para avisar al cliente redacta el mensaje y envíalo con `send_email` solo tras la confirmación expresa del usuario.
6. Resume: incidencias más antiguas, urgentes y próximos pasos.

## Cuidado

- No cierres una incidencia (`status: "Closed"`) sin que el usuario lo pida.
- No inventes datos del cliente ni compromisos de plazo.
