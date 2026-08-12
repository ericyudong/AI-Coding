"""Run the Legal Agent backend server."""
import sys

import uvicorn

from app.core.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    use_reload = bool(settings.debug) and sys.platform != "win32"
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=use_reload,
    )
