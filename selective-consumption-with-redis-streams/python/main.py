import importlib
import logging
import sys

from waitress import serve

from app import otel
from app.config import PORTS

COMPONENTS = ["producer", "consumer", "notifier"]


def main():
    component = sys.argv[1] if len(sys.argv) > 1 else ""
    if component not in COMPONENTS:
        sys.exit(f"usage: python main.py {{{'|'.join(COMPONENTS)}}}")

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    otel.setup(component)
    module = importlib.import_module(f"app.{component}")

    if component == "consumer":
        module.main()
    else:
        app = module.create_app()
        otel.instrument(app)
        serve(app, host="0.0.0.0", port=PORTS[component])


if __name__ == "__main__":
    main()
