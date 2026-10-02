# RRHH: ausencias y nóminas

## Pasos

1. Identifica al empleado con `search_documents` (`doctype: "Employee"`, `purpose: "link_value"`). Si el usuario habla de sí mismo, busca su ficha por su usuario.
2. Saldo de vacaciones: `list_documents` sobre `Leave Allocation` (`employee`, `leave_type`, `total_leaves_allocated`, `from_date`, `to_date`; `docstatus: 1`) y `aggregate_documents` sobre `Leave Application` con `sum` de `total_leave_days` filtrando `status: "Approved"`.
3. Para solicitar una ausencia, crea `Leave Application` con `create_document`: `employee`, `leave_type`, `from_date`, `to_date` y `description`. Déjala en borrador.
4. Nóminas: `list_documents` sobre `Salary Slip` (`employee`, `start_date`, `end_date`, `gross_pay`, `net_pay`; `docstatus: [0, 1]`).
5. Resume: días disponibles, solicitudes pendientes o importes de la nómina.

## Cuidado

- Son datos personales: muestra únicamente los del empleado que el usuario tiene derecho a ver.
- La aprobación (`leave_approver`) la decide la persona responsable; no la cambies por tu cuenta.
- No generes ni valides nóminas sin petición expresa.
