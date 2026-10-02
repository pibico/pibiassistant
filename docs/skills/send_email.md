# Cómo usar send_email

## Cuándo usarla

Para enviar un correo desde la cuenta de correo configurada en el sitio, cuando el usuario lo pide de forma explícita.

## Parámetros

| Parámetro | Obligatorio | Descripción |
|-----------|-------------|-------------|
| `recipients` | Sí | Lista de direcciones |
| `subject` | Sí | Asunto |
| `message` | Sí | Cuerpo del mensaje |
| `cc` | No | Lista de direcciones en copia |
| `send_as_html` | No | `true` si el cuerpo es HTML |

## Pasos

1. Redacta el mensaje y muéstraselo al usuario si el contenido es sensible o va a terceros.
2. Confirma destinatarios con `search_documents` (`purpose: "link_value"` sobre Contact o User) en lugar de inventar direcciones.
3. Envía una sola vez. El correo se pone en cola con la configuración SMTP del sitio.

## Cuidado

Nunca envíes datos de clientes a direcciones que el usuario no haya indicado.
