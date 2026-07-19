# Workshop Product Brand

Simple reusable spare-part Brand Master for Odoo 18 Community.

## Features

- Brand Name, optional Code, and archive support
- Optional Brand assignment on `product.template`
- An editable stored related Brand on `product.product`
- One shared Brand for every variant of the same product template
- Brand columns on Product and Product Variant lists and forms
- Product search and Group By Brand
- Optional indexed English Name beside the standard Myanmar Product Name
- Part Brands menu under Repairs > Configuration

The standard `product.template.name` remains the Product display name and is
labelled Myanmar Name in the Product title. `english_name` is optional,
copyable through standard Odoo behavior, visible in the Product list, and
available as a separate Product search field. Existing products do not require
backfilling.

Existing products without a Brand continue to work. During upgrade, a legacy
variant Brand is copied to its template. If old variants of one template have
different Brands, the Brand from the earliest variant is retained.

Brand types, country/origin, ordering sequences, approval states, and
multi-company UI are intentionally excluded from the normal module experience.

For safe upgrades without changing the existing security CSV, a minimal hidden
legacy Brand Type model and optional compatibility fields remain registered in
the backend. They have no menu, views, seed data, workflow, or business logic.

## Dependencies

- `base`
- `product`
- `repair`

## Menu

`Repairs > Configuration > Part Brands`

The existing Odoo Repair root and `repair.repair_menu_config` are reused.

## Upgrade

```text
odoo-bin -d <database> -u workshop_product_brand --stop-after-init
```

## License

LGPL-3
