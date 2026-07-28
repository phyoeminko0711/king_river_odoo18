# Purchase Sale Price Approval

## Overview

`purchase_sale_price_approval` is a custom Odoo 18 Community addon that introduces a controlled approval workflow for product sale price changes derived from validated Stock Landed Costs.

When a Landed Cost is validated, the module evaluates each affected product against configurable sale price rules using the final landed unit cost. Instead of updating `product.template.list_price` immediately, it creates a `Sale Price Update` record in **Pending** status only when the proposed sale price is greater than the current product sale price. A manager reviews the proposed price and decides whether to approve or reject it.

Only approved updates modify the product sales price.

## Business Problem

Organizations often want cost-driven pricing logic without allowing inventory costing operations to change live product sale prices without review. Direct automatic updates create operational risk:

- price changes can happen without review
- product-specific margin rules can be bypassed
- pricing changes become hard to audit
- re-confirmed or cancelled Purchase Orders can create inconsistent pricing behavior

This module solves that by separating:

1. **Calculation**
2. **Review**
3. **Approval**
4. **Audit trail**

## Features

- Sale price rule master with company and currency support
- Rule lines based on:
  - all products
  - product category
  - specific product template or variant
- Rule priority support:
  1. specific product variant
  2. specific product template
  3. exact product category
  4. parent category
  5. all products
- Amount range validation
- Date validity validation
- Overlapping rule prevention
- Landed Cost validation hook
- Pending `Sale Price Update` workflow
- Manager approval and rejection flow
- Batch approval and rejection wizard
- Immutable `Sale Price History`
- Chatter logging and review activities
- Multi-company filtering
- Currency conversion support
- Smart button on Purchase Orders
- Smart button on Landed Costs

## Installation

1. Place the module in your custom addons path:

   `D:\odoo18_custom_addons\purchase_sale_price_approval`

2. Make sure `D:\odoo18_custom_addons` is included in `addons_path` inside `odoo.conf`.

3. Restart Odoo.

4. Update the apps list.

5. Install **Purchase Sale Price Approval**.

## Configuration

Go to:

`Purchase -> Configuration -> Settings`

Find the **Sale Price Approval** section and configure:

- **Enable Sale Price Approval**
- **Include Service Products**
- **Allow Manual Approved Price**
- **Block Price Decrease**
- **Sale Price Rounding**
- **Approval Activity Users**

### Rule Setup

Go to:

`Purchase -> Configuration -> Sale Price Management -> Sale Price Rules`

Create one or more rules and activate them.

Each rule contains pricing lines with:

- amount range
- applicability scope
- markup type
- markup value
- validity dates
- priority

## Rule Priority

Rule selection follows this order:

1. Specific product variant
2. Specific product template
3. Exact product category
4. Parent product category
5. All products

Within the same scope, the module chooses:

1. Lowest priority number
2. Lowest sequence
3. Latest valid-from date
4. Highest record ID as a deterministic fallback

## Landed Cost Validation Workflow

When a Stock Landed Cost is validated:

1. Odoo validates the Landed Cost first.
2. Validated valuation adjustment lines are grouped by product.
3. The module calculates weighted landed unit cost from original inventory value plus allocated landed costs.
4. The best matching pricing rule is selected.
5. A proposed selling price is calculated.
6. A `Sale Price Update` record is created in **Pending** state only when the proposed price is higher than the current sale price.
7. The Landed Cost chatter receives a note.
8. Review activities are scheduled for Sale Price Managers.

Important:

- Purchase Order confirmation does **not** create Sale Price Updates
- the module does **not** use `purchase.order.line.price_unit` as the cost basis for new updates
- the module does **not** update `product.template.list_price` at Landed Cost validation time

## Approval Workflow

Pending updates are reviewed from:

`Purchase -> Configuration -> Sale Price Management -> Sale Price Updates`

Manager actions:

- **Approve**
- **Reject**
- **Cancel**
- **Reset to Pending**

### On Approval

The module:

1. validates the approved sale price
2. checks configured restrictions
3. updates `product.template.list_price`
4. marks the update as **Approved**
5. records approver and approval date
6. posts chatter messages
7. creates a `Sale Price History` record

### On Rejection

- rejection reason is required
- product sale price remains unchanged
- update becomes **Rejected**

### On Cancellation

- only pending updates can be cancelled
- product sale price remains unchanged

## Calculation Logic

Source cost amount:

- weighted landed unit cost from `stock.valuation.adjustment.lines`
- original inventory value and allocated landed costs are included

Calculation formulas:

### Percentage

```text
new_sale_price = landed_unit_cost + (landed_unit_cost * markup_value / 100)
```

### Fixed Amount

```text
new_sale_price = landed_unit_cost + markup_value
```

If a rounding value is configured, the calculated result is rounded to the nearest configured value before currency rounding is applied.

## Example

Landed Unit Cost:
`1,500,000 MMK`

Rule:
`1,000,000 <= Price <= 2,000,000`

Markup:
`10%`

Calculated Sale Price:
`1,650,000 MMK`

Workflow:

`Landed Cost Validate -> Pending Sale Price Update -> Manager Review -> Approve -> Product Sales Price Updated`

## User Roles

### Sale Price User

- read rules
- read updates
- read history
- cannot approve or reject

### Sale Price Manager

- manage rules
- approve and reject updates
- run batch approval
- read history

### Sale Price Administrator

- full access to rules and updates
- administrative control over the module
- history remains immutable except for system administrators deleting records

## Multi-Company Behavior

- rules, updates, and history records are company-specific
- users only see records for their allowed companies
- product sale prices are read and written with `with_company(company_id)`
- Landed Costs only generate updates in their own company context

## Currency Behavior

- Landed Costs use the company currency for valuation data
- the module converts landed unit cost using `res.currency._convert()` when rule currency differs
- both source and converted landed costs are stored
- range matching uses the rule currency

## Purchase Order Cancellation Behavior

When a Purchase Order is cancelled:

- related pending updates are marked **Cancelled**
- approved updates stay **Approved**
- product sales price is not reverted automatically
- chatter notes are posted for audit clarity

Purchase Order confirmation and done actions do not create new Sale Price Updates. Existing historical Purchase Order based records remain valid for audit compatibility.

## Known Limitations

- the module updates the standard `list_price` field and does not integrate with Odoo Pricelists
- historical records are immutable by design
- approval locking uses a conservative database row lock during approval
- the test suite is focused on business logic rather than UI rendering

## Testing

Run the module tests with Odoo, for example:

```bash
odoo-bin -d <test_db> -i purchase_sale_price_approval --test-enable --stop-after-init
```

For upgrade testing:

```bash
odoo-bin -d <test_db> -u purchase_sale_price_approval --test-enable --stop-after-init
```

## Technical Summary

Main models:

- `sale.price.rule`
- `sale.price.rule.line`
- `sale.price.update`
- `sale.price.history`

Main hooks:

- `stock.landed.cost.button_validate()`
- `purchase.order.button_cancel()`

Main outcome:

- Purchase Order confirmation never creates Sale Price Updates
- Landed Cost validation creates Sale Price Updates only for price increases
- Manager approval is required before `product.template.list_price` is updated

## License

LGPL-3
