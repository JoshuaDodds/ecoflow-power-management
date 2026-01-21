#!/usr/bin/env python3
import multiprocessing
import time
import os
import sys
import logging
import importlib.util

# Import version
try:
    from __version__ import __version__
except ImportError:
    __version__ = "unknown"

# Load environment variables from .env file
from utils import env_loader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("orchestrator")

# Define known services and their entry points
# Format: (Service Name, Relative Path to File, Module Name)
KNOWN_SERVICES = [
    ("soc_bridge", "services/soc_bridge.py", "services.soc_bridge"),
    ("policy_engine", "services/policy_engine.py", "services.policy_engine"),
    ("ecoflow_cloud", "services/ecoflow_cloud_bridge.py", "services.ecoflow_cloud_bridge"),
]


def run_service(name, file_path, module_name):
    """
    Worker function to load and run a service module.
    """
    service_logger = logging.getLogger(name)
    service_logger.info(f"Launching {name} from {file_path}...")

    try:
        # Dynamic import to run the module's main() function
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            service_logger.error(f"Could not load spec for {file_path}")
            return

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # Assume every service has a main() function
        if hasattr(module, "main"):
            module.main()
        else:
            service_logger.error(f"No main() function found in {file_path}")

    except Exception as e:
        service_logger.exception(f"Service {name} crashed: {e}")


def main():
    logger.info(f"--- EcoFlow Power Management Orchestrator v{__version__} Starting ---")
    
    # Validate configuration before starting services
    from utils.config_validator import ConfigValidator
    ConfigValidator.validate_all()
    ConfigValidator.print_config_summary()

    processes = []

    for name, path, mod_name in KNOWN_SERVICES:
        if os.path.exists(path):
            logger.info(f"Found service: {name}")
            p = multiprocessing.Process(target=run_service, args=(name, path, mod_name), name=name)
            p.start()
            processes.append(p)
        else:
            logger.warning(f"Skipping {name}: File not found at {path}")

    if not processes:
        logger.error("No services found to start! Check your paths.")
        sys.exit(1)

    logger.info(f"All available services started. Monitoring {len(processes)} processes...")

    try:
        # Keep the main process alive to monitor children
        while True:
            time.sleep(5)
            # Optional: Check if processes are still alive and restart them if needed
            for p in processes:
                if not p.is_alive():
                    logger.error(f"Service {p.name} has died!")
                    # In a real supervisor, you would restart it here.

    except KeyboardInterrupt:
        logger.info("Shutting down...")
        for p in processes:
            p.terminate()
            p.join()


if __name__ == "__main__":
    main()