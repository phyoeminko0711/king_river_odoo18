# Workshop Customer Vehicle

Simple Customer Vehicle Master for Odoo 18 Community workshop operations.

Customer vehicles are individual customer assets. They remain completely
separate from Products, product variants, lots, and Odoo Fleet.

## Normal user interface

- Customer
- Vehicle Brand and filtered Vehicle Model
- Plate, chassis, and engine numbers
- Color and mileage
- Active/archive status
- Contact smart button for related vehicles
- Repairs menus for Vehicles, Vehicle Brands, and Vehicle Models

The internal vehicle reference, model year, mileage unit, transmission, fuel
type, vehicle photo, notes, chatter support, and Job Card integration fields are
retained in Python for compatibility and future use but hidden from the normal
vehicle form.

## Validation

- Plate Number is required.
- Mileage cannot be negative.
- Vehicle Model must belong to the selected Vehicle Brand.
- Customer and Plate Number combinations must be unique.

## Access

The existing security configuration is unchanged. Repair users maintain customer
vehicles, while Repair managers maintain Vehicle Brand and Model masters.

## Tests

```text
odoo-bin -d <database> -i workshop_customer_vehicle --test-enable --stop-after-init
```

