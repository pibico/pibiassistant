# Estado del pipeline comercial (CRM)

## Pasos

1. Oportunidades abiertas por etapa: `aggregate_documents` sobre `Opportunity` con `count` y `sum` de `opportunity_amount`, agrupado por `sales_stage`, filtrando `status: "Open"`.
2. Oportunidades que más pesan: `list_documents` ordenado por `opportunity_amount desc`, con `party_name`, `sales_stage`, `expected_closing`.
3. Leads recientes sin atender: `list_documents` sobre `Lead` con `status: "Lead"` ordenado por `creation`.
4. Oportunidades vencidas: `expected_closing` anterior a hoy y aún abiertas.
5. Presenta tabla por etapa, total ponderado si hay `probability`, y tres acciones recomendadas.

## Cuidado

Distingue importe total de importe ponderado. No inventes probabilidades.
