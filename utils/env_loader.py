import os


def load_env():
    """
    Searches for a .env file in the project root (up to 2 levels up)
    and loads variables into os.environ.
    Supports multi-line values enclosed in quotes.
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
            lines = f.readlines()
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    i += 1
                    continue

                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Strip inline comments (everything after # that's not in quotes)
                    if '#' in value and not (value.startswith('"') or value.startswith("'")):
                        value = value.split('#')[0].strip()

                    # Handle multi-line values (JSON, etc.)
                    if value.startswith(('"', "'")):
                        quote_char = value[0]
                        # Check if value ends with matching quote
                        if not value.endswith(quote_char):
                            # Multi-line value - collect until closing quote
                            i += 1
                            while i < len(lines):
                                next_line = lines[i].rstrip()
                                value += '\n' + next_line
                                if next_line.endswith(quote_char):
                                    break
                                i += 1

                        # Remove surrounding quotes
                        if (value.startswith('"') and value.endswith('"')) or \
                                (value.startswith("'") and value.endswith("'")):
                            value = value[1:-1]
                    
                    # Final trim
                    value = value.strip()

                    # Only set if not already set (don't overwrite system env vars)
                    if key not in os.environ:
                        os.environ[key] = value
                
                i += 1
    except Exception as e:
        print(f"Error loading .env: {e}")


# Automatically load when imported?
# Usually better to be explicit, but for this use case, auto-load on import is convenient.
load_env()