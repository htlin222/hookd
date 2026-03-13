import argparse
import logging
import signal
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from hookd.constants import DEFAULT_PORT
from hookd.listener.server import create_server

logger = logging.getLogger("hookd")


def main():
    parser = argparse.ArgumentParser(description="hookd webhook listener")
    parser.add_argument("--config", required=True, help="Path to config.yaml")
    parser.add_argument("--port", type=int, default=None, help="Port to listen on")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    config_path = Path(args.config)
    if not config_path.exists():
        logger.error("Config file not found: %s", config_path)
        sys.exit(1)

    # Load .env from same directory as config
    env_path = config_path.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    import os
    secret = os.environ.get("HOOKD_SECRET", "")
    if not secret:
        logger.error("HOOKD_SECRET not set. Set it in .env or environment.")
        sys.exit(1)

    port = args.port or int(os.environ.get("HOOKD_PORT", str(DEFAULT_PORT)))

    with open(config_path) as f:
        config = yaml.safe_load(f) or {}

    workdir = config_path.parent.parent  # .hookd/../
    server = create_server(config, secret, port, workdir)

    def shutdown(signum, frame):
        logger.info("Shutting down...")
        server.shutdown()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    logger.info("hookd listening on port %d", port)
    logger.info("Config: %s", config_path)
    logger.info("Workdir: %s", workdir)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        logger.info("Server stopped.")


if __name__ == "__main__":
    main()
