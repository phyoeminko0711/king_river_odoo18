# Workshop Job Card

An Odoo 18 Community Job Card for customer-owned vehicles with the workflow:

`Draft -> Sent to Customer -> Approved -> Repair Order Created`

Sent Job Cards may be Rejected. Draft, Sent, and Approved Job Cards can be
Cancelled, while Rejected and Cancelled Job Cards can return to Draft.

Repair Options are entered directly in one table with service, product, Brand,
part number, warranty, quantity, UoM, price, amount, and customer selection.
Selecting a product fills its UoM and sales price. Only one option can be
selected for the same service, and the Job Card shows selected count and total.

Each Job Card can also hold multiple `workshop.job.card.service` headers linked
to the reusable `workshop.repair.service` master. Each header owns its Product
Option lines and computes its selected option and selected amount. Option lines
now require a service-line parent; their Job Card and Repair Service are stored
related fields. The former text service column remains as a readonly related
compatibility value.

Selecting a Repair Service automatically generates one Product Option for each
directly linked product. The same helper runs for form onchange and backend
create/write operations, avoids duplicates, and preserves edited quantity and
price when a product is shared by the old and new service.

The Job Card form shows an editable Repair Services list above one flat Product
Options table. Generated products and service names are readonly, Draft users
may edit warranty, quantity, UoM, and price, and option selection remains open
in Draft and Sent. The footer shows only the selected-option Total.

The inline Repair Service list persists only the selected service and sequence;
backend generation then creates complete Product Option rows. This avoids empty
nested One2many commands while retaining model-level onchange support.

`total_amount` is the stored Job Card Total used by the form and list views. It
sums only selected Product Options; unselected generated alternatives never
contribute. The former `selected_total` and selected-line count remain as hidden
compatibility fields.

Each Repair Service permits exactly one selected Product Option. Selecting a
different sibling immediately clears the previous selection in the form and
through backend create/write operations. A validation fallback protects import
and RPC operations from leaving duplicate selections.

Sending requires at least one Repair Service and at least one Product Option on
every service. Approval requires exactly one selected option per service; when
choices are missing, the validation message lists the affected Repair Services.

Approved Job Cards create exactly one standard `repair.order`. Only selected
Repair Options are transferred as standard `stock.move` Add component lines.
The Repair customer and scheduled date come from the Job Card, and reciprocal
links connect the two documents.

Repair Order creation revalidates that every Repair Service has exactly one
selection, then transfers only those selected option lines with their product,
quantity, UoM, and unit price. Repair Services and customer vehicles are never
used as Repair products.

Odoo 18 does not require `repair.order.product_id`. This integration deliberately
leaves it empty because the customer-owned vehicle is not an inventory product.
The vehicle stays linked through `customer_vehicle_id`; no generic or vehicle
product is created.

No invoices, labour rates, employee costs, approval history, portal access, or
digital signatures are included. Approved and Repair-created Job Cards and
their option lines remain protected from business-data changes. Legacy service
and option tables remain registered only for upgrade compatibility and are not
shown in the Job Card UI.

When Odoo demo data is enabled, the module provides Front Brake Repair and
Engine Oil Change services, three product alternatives for each, and a Draft
Job Card containing both services. No sample records are loaded in production
databases created without demo data.
