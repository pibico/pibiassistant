# pibiAssistant

> Habla con tu sitio ERPNext. pibiAssistant permite a Claude, ChatGPT y otros
> LLMs compatibles con MCP trabajar directamente con tus facturas, clientes,
> stock, flujos de trabajo y apps personalizadas — dentro de los permisos de
> ERPNext, con cada llamada registrada.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://github.com/pibico/pibiassistant)
[![License](https://img.shields.io/badge/license-AGPL--3.0-green)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-2025--06--18-orange)](https://modelcontextprotocol.io)
[![Tools](https://img.shields.io/badge/tools-34-brightgreen)](#tools-at-a-glance)

---

## AIDA Chat

pibiAssistant incluye **AIDA** (Asistente Inteligente De pibiCo) — un chat
integrado en Frappe Desk y una SPA en `/aida`, conectado a las APIs de pibiCo
en `api.espib.co`.

- **Widget en el Desk**: aparece en cada página de Frappe Desk.
- **SPA completa**: disponible en `/aida` con historial, streaming y herramientas.
- **Conversión de documentos**: PDF/imágenes a markdown vía API Docling.
- **Transcripción de voz**: audio a texto vía API Whisper.

### Configuración

1. Abre **PA Core Settings** en el Desk.
2. En la pestaña **AIDA Chat**, activa el checkbox y configura las APIs:
   - **Chat API**: URL y API key del servicio LLM
   - **Convert API**: URL y API key del servicio de conversión
   - **Voice API**: URL y API key del servicio de transcripción
3. Pulsa **Refresh Models** para cargar providers y modelos disponibles.
4. Pulsa **Test AIDA APIs** para verificar conectividad.

No requiere `bench restart` — el toggle se aplica inmediatamente.

---

## Servidor MCP (BYO-LLM)

pibiAssistant es también un servidor MCP completo. Conecta cualquier
cliente MCP (Claude Desktop, Cursor, ChatGPT desktop, MCP Inspector) a
tus datos de Frappe/ERPNext. Tú eliges el LLM y pagas tu propia factura.

### Instalación

```bash
cd frappe-bench
bench get-app https://github.com/pibico/pibiassistant
bench --site <tu-sitio> install-app pibiassistant
```

Requiere Frappe v15 o v16 y Python 3.10+. Node 22+ necesario para
compilar la interfaz de chat.

### Conectar tu LLM

1. Ve a **PA Core Settings** y copia la **MCP Endpoint URL**.
2. En **Claude Desktop → Settings → Connectors → Add Custom Connector**,
   pega la URL y haz click en **Add**.
3. Click en **Connect**, inicia sesión con tu cuenta ERPNext y autoriza.
4. Pregunta algo — por ejemplo, *"Lista todas las facturas pendientes."*

---

## Qué obtienes

Expone **34 herramientas** para las operaciones diarias:

| Categoría | Herramientas |
|---|---|
| Documentos | `get_document`, `list_documents`, `create_document`, `update_document`, `delete_document`, `submit_document` |
| Búsqueda | `search_documents`, `search`, `fetch` |
| Totales | `aggregate_documents` |
| Reportes | `report_list`, `report_requirements`, `generate_report` |
| Aprobaciones | `get_pending_approvals`, `run_workflow` |
| Schema | `get_doctype_info` |
| Analítica | `run_python_code`, `run_database_query`, `analyze_business_data` |
| Archivos | `extract_file_content`, `attach_file`, `create_upload_link`, `generate_document` |
| Correo | `send_email` |
| Skills | `get_skill` |
| Navegador | `browser_get_page_context`, `browser_get_form_data`, `browser_navigate_to`, `browser_wait_for_page`, `browser_take_screenshot`, `browser_capture_diagnostics` |
| Dashboards | `create_dashboard`, `create_dashboard_chart`, `list_user_dashboards` |

---

## Skills y Prompt Templates

**Skills** son instrucciones reutilizables almacenadas como documentos
`PA Skill`. Cada skill tiene un `skill_id`, descripción y contenido
markdown. El LLM los consulta bajo demanda.

**Prompt Templates** son puntos de partida con argumentos tipados
(dropdowns, fechas, booleanos). Los autores los publican desde el admin;
los usuarios eligen uno, completan los argumentos y el prompt se envía
al LLM.

---

## Schema en vivo

pibiAssistant lee el schema desde la API de metadatos de Frappe en cada
llamada. No mantiene copia propia — DocTypes personalizados, Custom Fields
y Property Setters son visibles inmediatamente. Los permisos se evalúan
por llamada contra el usuario solicitante.

---

## Extiende con tus propias herramientas

Usa el hook `assistant_tools` en el `hooks.py` de tu app Frappe. Las
herramientas viajan con la app, sobreviven actualizaciones y están
limitadas a tu modelo de datos. El mismo patrón funciona para Skills
vía el hook `assistant_skills`.

---

## Autenticación y seguridad

OAuth 2.0 con PKCE — el LLM nunca ve la contraseña del usuario. Cada
llamada está limitada a los roles y permisos del usuario en Frappe/ERPNext.
Cada operación se registra en `PA Audit Log`.

---

## Licencia

AGPL-3.0 — ver [LICENSE](LICENSE).

## Contribuir

Contribuciones bienvenidas. Ver [Contributing.md](Contributing.md).
