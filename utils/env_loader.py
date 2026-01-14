import os


def load_env():
    """
    Searches for a .env file in the project root (up to 2 levels up)
    and loads variables into os.environ.
    """
    # Start from the file's current location and go up
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Check current, parent, and grandparent directories for .env
    possible_paths = [
        os.path.join(current_dir, '.env'),
        os.path.join(os.path.dirname(current_dir), '.env'),
        os.path.join(os.path.dirname(os.path.dirname(current_dir)), '.env')
    ]

    env_path = None
    for path in possible_paths:
        if os.path.exists(path):
            env_path = path
            break

    if not env_path:
        # Silent fail or print warning? Silent is usually better for prod,
        # but for this setup we want to know.
        # print("Info: No .env file found.")
        return

    try:
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()

                    # Remove surrounding quotes
                    if (value.startswith('"') and value.endswith('"')) or \
                            (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]

                    # Only set if not already set (don't overwrite system env vars)
                    if key not in os.environ:
                        os.environ[key] = value
    except Exception as e:
        print(f"Error loading .env: {e}")


# Automatically load when imported?
# Usually better to be explicit, but for this use case, auto-load on import is convenient.
load_env()