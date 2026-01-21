"""Version information for EcoFlow Power Management"""
import os
from datetime import datetime

def get_version():
    """
    Get version dynamically at runtime.
    
    Priority:
    1. APP_VERSION environment variable (set by Docker build)
    2. Git describe (for local development)
    3. Fallback to CalVer-dev
    
    Format: YYYY.MM.DD-BUILD
    Example: 2026.01.21-1234
    """
    # 1. Check if running in container (version baked in at build time)
    version = os.environ.get('APP_VERSION')
    if version:
        return version
    
    # 2. Check if git tag/describe exists (for local dev)
    try:
        import subprocess
        result = subprocess.run(
            ['git', 'describe', '--tags', '--always', '--dirty'],
            capture_output=True,
            text=True,
            timeout=1,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        if result.returncode == 0:
            tag = result.stdout.strip()
            # If it's a commit hash (no tags), format as CalVer-dev-hash
            if '-' not in tag and len(tag) == 7:
                now = datetime.now()
                return f"{now.strftime('%Y.%m.%d')}-dev-{tag}"
            return tag
    except Exception:
        pass
    
    # 3. Fallback: Generate CalVer-dev
    now = datetime.now()
    return f"{now.strftime('%Y.%m.%d')}-dev"

__version__ = get_version()
__author__ = "Joshua Dodds"
__license__ = "MIT"
