# Estados financieros

## Pasos

1. Empresa y ejercicio: los que indique el usuario; si no, la empresa por defecto y el último `Fiscal Year`. Consulta `report_requirements` del informe si dudas de un filtro.
2. Cuenta de resultados: `generate_report` con `Profit and Loss Statement` (`company`, `filter_based_on: "Fiscal Year"`, `from_fiscal_year`, `to_fiscal_year`, `periodicity`: `Yearly`, `Quarterly` o `Monthly`).
3. Balance de situación: `Balance Sheet` con los mismos filtros.
4. Balance de sumas y saldos: `Trial Balance` con `company` y `fiscal_year`; comprueba que debe y haber coinciden.
5. Tesorería: `Cash Flow` con los filtros de la cuenta de resultados.
6. Para un periodo que no sea un ejercicio, usa `filter_based_on: "Date Range"` con `period_start_date` y `period_end_date`.
7. Resume en una tabla con los grupos principales (ingresos, gastos, resultado; activo, pasivo, patrimonio), la cifra clave y la variación frente al periodo anterior si el usuario la pide.

## Cuidado

Son cifras contables del sitio, sin ajustes de cierre: indica que un asiento sin validar no aparece. No mezcles el valor de un filtro de un informe con el de otro.
