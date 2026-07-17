# Workshop Job Card

An Odoo 18 Community Job Card for customer-owned vehicles with the workflow:

`Draft -> Sent to Customer -> Approved -> Repair Order Created`

Sent Job Cards may be Rejected. Draft, Sent, and Approved Job Cards can be
Cancelled, while Rejected and Cancelled Job Cards can return to Draft.

Repair Options are entered directly in one table with service, product, Brand,
part number, warranty, quantity, UoM, price, amount, and customer selection.
Selecting a product fills its UoM and sales price. Only one option can be
selected for the same service, and the Job Card shows selected count and total.

Approved Job Cards create exactly one standard `repair.order`. Only selected
Repair Options are transferred as standard `stock.move` Add component lines.
The Repair customer and scheduled date come from the Job Card, and reciprocal
links connect the two documents.

Odoo 18 does not require `repair.order.product_id`. This integration deliberately
leaves it empty because the customer-owned vehicle is not an inventory product.
The vehicle stays linked through `customer_vehicle_id`; no generic or vehicle
product is created.

No invoices, labour rates, employee costs, approval history, portal access, or
digital signatures are included. Approved and Repair-created Job Cards and
their option lines remain protected from business-data changes. Legacy service
and option tables remain registered only for upgrade compatibility and are not
shown in the Job Card UI.
