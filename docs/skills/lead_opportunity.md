# Alta de lead y oportunidad

## Pasos

1. Busca duplicados con `search_documents` sobre `Lead` por nombre, empresa o correo (`email_id`). Si ya existe, usa ese registro.
2. Revisa los campos con `get_doctype_info` (`Lead`).
3. Crea el lead con `create_document` (`Lead`): `first_name` o `lead_name`, `company_name`, `email_id`, `mobile_no` y `source` si se conoce.
4. Si hay interés comercial concreto, crea la oportunidad con `create_document` (`Opportunity`): `opportunity_from: "Lead"`, `party_name` con el nombre del lead, `opportunity_amount` y `expected_closing`.
5. Resume: lead y oportunidad creados, estado (`status`) y siguiente paso propuesto.

## Cuidado

- No inventes datos de contacto ni importes: deja vacío lo que el usuario no haya dicho.
- Un lead que ya es cliente no se duplica; usa el `Customer` existente con la skill party-by-nif.
