# Sales Team Warehouse

Odoo 18 Community addon that links each Sales Team to one default Warehouse and
uses that warehouse on quotations and sales orders.

## Behavior

- Configure a Warehouse on a Sales Team.
- When the Sales Team is selected on a quotation or sales order, the Warehouse is
  filled from the Sales Team.
- If the Sales Team has no Warehouse, the current or standard Odoo default
  Warehouse is kept.
- Backend create/write flows also apply the mapping for imports, RPC calls, and
  automated actions.
- If a process explicitly supplies `warehouse_id`, that value is preserved.

## Configuration

Go to Sales or CRM configuration, open Sales Teams, and set the Warehouse field.

Example:

- Sales Team: Yangon Sales Team
- Warehouse: Yangon Warehouse

## Notes

The module keeps Warehouse editable on sale orders so managers can manually
override it when needed. No custom security rules are added in this phase.
