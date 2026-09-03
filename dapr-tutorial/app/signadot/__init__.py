"""
Signadot platform layer.

Everything Signadot-specific lives here, so application code (frontend,
checkout, order_processor) stays ordinary Dapr code:

  routing.py     where the routing key lives and how to forward it
  routes_api.py  selective consumption via the Signadot Routes API
"""
