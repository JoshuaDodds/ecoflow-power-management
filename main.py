#!/usr/bin/env python3
import argparse
import sys
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("main")

def run_soc_bridge():
    logger.info("Starting SoC Bridge Service...")
    from services.soc_bridge import main as bridge_main
    bridge_main()

def run_policy_engine():
    logger.info("Starting Policy Engine...")
    # Import inside the function to avoid errors if the file doesn't exist yet
    try:
        from services.policy_engine import main as policy_main
        policy_main()
    except ImportError:
        logger.error("Policy Engine service not found or implemented yet.")
        sys.exit(1)

def run_agent():
    logger.info("Starting Host Agent...")
    try:
        from agents.host_agent import main as agent_main
        agent_main()
    except ImportError:
        logger.error("Host Agent not found or implemented yet.")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="EcoFlow Power Management Unified Entrypoint")
    parser.add_argument(
        "service", 
        choices=["soc_bridge", "policy_engine", "agent"],
        help="The service to run"
    )
    
    args = parser.parse_args()

    if args.service == "soc_bridge":
        run_soc_bridge()
    elif args.service == "policy_engine":
        run_policy_engine()
    elif args.service == "agent":
        run_agent()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Shutdown requested.")
        sys.exit(0)
