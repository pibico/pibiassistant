# Cómo usar las herramientas de navegador

Las herramientas `browser_*` actúan sobre la pestaña del usuario y solo funcionan si el usuario tiene Frappe abierto.

| Necesitas | Herramienta |
|-----------|-------------|
| Saber qué está viendo el usuario | `browser_get_page_context` |
| Leer los campos de un formulario abierto | `browser_get_form_data` |
| Abrir un documento, lista o informe | `browser_navigate_to` (solo rutas del mismo sitio) |
| Esperar a que cargue la página o aparezca un texto | `browser_wait_for_page` |
| Ver un gráfico o una maqueta | `browser_take_screenshot` |
| Diagnosticar un error en pantalla | `browser_capture_diagnostics` |

## Pasos recomendados

1. Antes de ayudar con lo que ve el usuario, llama a `browser_get_page_context`.
2. Tras `browser_navigate_to`, llama a `browser_wait_for_page` antes de leer nada.
3. Si el usuario dice que algo falla, usa `browser_capture_diagnostics` y no una captura simple: incluye errores de consola y peticiones fallidas.
4. Para datos usa las herramientas de documentos; el navegador no sustituye a `get_document` ni a `list_documents`.
