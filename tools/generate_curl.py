import os
import time
import hmac
import hashlib
import random
import sys

# Load .env manually to be standalone
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if os.path.exists(env_path):
    with open(env_path, 'r') as f:
        for line in f:
            if line.strip() and not line.startswith('#') and '=' in line:
                k, v = line.strip().split('=', 1)
                os.environ[k] = v.strip().strip("'").strip('"')

ACCESS_KEY = os.getenv("ECOFLOW_ACCESS_KEY", "")
SECRET_KEY = os.getenv("ECOFLOW_SECRET_KEY", "")
HOST = "https://api-e.ecoflow.com"

def get_signed_url(endpoint, params):
    # 1. Add Auth Params
    params["accessKey"] = ACCESS_KEY
    params["nonce"] = str(random.randint(100000, 999999))
    params["timestamp"] = str(int(time.time() * 1000))
    
    # 2. Sort & Build String
    sorted_keys = sorted(params.keys())
    sign_str = "&".join([f"{k}={params[k]}" for k in sorted_keys])
    
    # 3. Sign
    signature = hmac.new(
        SECRET_KEY.encode('utf-8'),
        sign_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # 4. Return Full URL
    return f"{HOST}{endpoint}?{sign_str}&sign={signature}"

def main():
    if not ACCESS_KEY or not SECRET_KEY:
        print("Error: Missing ECOFLOW_ACCESS_KEY/SECRET_KEY in .env")
        return

    if len(sys.argv) < 2:
        print("Usage: python tools/generate_curl.py [list|quota <sn>]")
        return

    mode = sys.argv[1]

    if mode == "list":
        # Test 1: List Devices (GET)
        url = get_signed_url("/iot-open/sign/device/list", {})
        print(f"\n--- COPY AND RUN THIS CURL COMMAND ---\n")
        print(f"curl -v \"{url}\"")
        print(f"\n--------------------------------------\n")

    elif mode == "quota":
        # Test 2: Get Quota (POST) - This is the Wake Up command
        if len(sys.argv) != 3:
            print("Usage: python tools/generate_curl.py quota <DEVICE_SN>")
            return
        sn = sys.argv[2]
        
        # For POST, we sign ONLY the query params (Auth), not the body
        url = get_signed_url("/iot-open/sign/device/quota", {})
        
        # The body is standard JSON
        body = f'{{"sn": "{sn}", "params": {{"cmdId": 0, "quotas": []}}}}'
        
        print(f"\n--- COPY AND RUN THIS CURL COMMAND ---\n")
        print(f"curl -v -X POST \"{url}\" \\")
        print(f"  -H \"Content-Type: application/json\" \\")
        print(f"  -d '{body}'")
        print(f"\n--------------------------------------\n")

if __name__ == "__main__":
    main()

