#!/usr/bin/env python3
"""
Test script to verify Pushover notifications work
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment
from utils import env_loader
from utils.notifier import Notifier

def main():
    print("Testing Pushover notifications...")
    print(f"PUSHOVER_ENABLED: {os.getenv('PUSHOVER_ENABLED')}")
    print(f"PUSHOVER_USER_KEY: {os.getenv('PUSHOVER_USER_KEY', '')[:8]}***")
    print(f"PUSHOVER_API_TOKEN: {os.getenv('PUSHOVER_API_TOKEN', '')[:8]}***")
    
    notifier = Notifier()
    
    print("\nSending test notification...")
    notifier.send("This is a test notification from EcoFlow Power Management", 
                  priority=0, 
                  title="Test Notification")
    
    print("Done! Check your Pushover app.")

if __name__ == "__main__":
    main()
