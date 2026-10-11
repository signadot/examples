## Base Prompt 1

Make the location service's response return the id field as a JSON string instead of a number and ensure unit tests pass.

## Base Prompt 2

Implement a "Fare Estimate + Ride History" feature across 3 services:

1. Driver service (services/driver/):
- After finding the best driver, compute a fare from the route ETA ($1.50/minute, minimum $3.50)
- Include the fare in the existing driver notification body so the frontend can parse it

2. Location service (services/location/):
- Add a ride_history table to MySQL: pickup location name, dropoff location name, request time, driver plate, and fare amount
- Add GET /ride-history (returns list + total count), POST /ride-history (creates entry), and PATCH /ride-history (updates driver plate and fare after assignment)

3. Frontend service (services/frontend/):
- Proxy the ride-history endpoints to the location service
- In the React UI, parse the fare from the driver notification and display it in the ETA countdown
- Add a "Ride History" card below the ride form showing a table of past rides (pickup, dropoff, time, plate, fare) with a total count
- After dispatching, create a ride-history entry. When the driver notification arrives with plate + fare, update the entry via PATCH

## Base Prompt 3

Make the location service's response return the id field as a JSON string called locID instead of a number, and rename name to id and validate your work

Make the location service's response return the id field as a JSON string called locID instead of a number, and rename name to id, and validate your work with /signadot-validate

## Base Prompt 4

Implement free shipping when cart subtotal ≥ $50 USD

## Base Prompt 5

In the product catalog service, rename id to sku and rename name to id and validate & fix it locally.

In the product catalog service, rename id to sku and rename name to id and validate & fix it with /signadot-validate on the demo cluster.

## Base Prompt 6

In the currencyservice, our JS style guide requires camelCase for object keys. Please convert any snake_case keys to camelCase and validate it works.

## With Signadot

verify with /signadot-validate and playwright on the demo cluster
