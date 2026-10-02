# Cómo usar attach_file

## Cuándo usarla

Para adjuntar un archivo a un documento que ya existe, por ejemplo el PDF original de una factura de compra justo después de crearla.

## Parámetros

| Parámetro | Obligatorio | Descripción |
|-----------|-------------|-------------|
| `doctype` | Sí | DocType del documento (`"Purchase Invoice"`) |
| `docname` | Sí | Nombre (id) del documento |
| `file_url` | Uno de los dos | URL de un archivo que ya está en Frappe (`/files/...` o `/private/files/...`) |
| `content_base64` + `filename` | Uno de los dos | Contenido en base64 de un archivo pequeño (máx. 10 MB) |
| `is_private` | No | Por defecto `true` |

## Pasos

1. Si el usuario subió el archivo al chat, usa el `file_url` que te indica el chat. No vuelvas a subirlo.
2. Crea primero el documento y adjunta después, con el `name` devuelto por `create_document`.
3. Indica solo una fuente: `file_url` o `content_base64`, nunca las dos.
4. Si el archivo solo existe en el disco del cliente, usa `create_upload_link`.

## Errores habituales

- Falta de permiso de escritura sobre el documento: informa al usuario, no reintentes.
- Tipo de archivo no permitido: se admiten pdf, imágenes, txt, csv, json, xml y documentos de Office.
