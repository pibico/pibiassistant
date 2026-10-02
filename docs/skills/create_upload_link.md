# Cómo usar create_upload_link

## Cuándo usarla

Cuando el archivo está en el disco del cliente (por ejemplo Claude Code) y no en Frappe. Devuelve una URL de un solo uso, válida 15 minutos, para un archivo de hasta 10 MB.

## Pasos

1. Crea el documento al que irá el archivo (`create_document`).
2. Llama a `create_upload_link` con `doctype` y `docname`. Usa `is_private: false` solo si el archivo debe ser público.
3. Ejecuta el comando `curl` devuelto sustituyendo la ruta del archivo.
4. Comprueba la respuesta: `success: true`. El enlace no se puede reutilizar; si falla, pide uno nuevo.

## Notas

- Si el archivo ya está en Frappe o es pequeño, usa `attach_file`.
- Un POST sin archivo no gasta el enlace.
