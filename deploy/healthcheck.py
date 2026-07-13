"""Docker healthcheck script."""
import sys
try:
    import httpx
    r = httpx.get("http://localhost:8000/health", timeout=5)
    sys.exit(0 if r.status_code == 200 else 1)
except Exception:
    sys.exit(1)
