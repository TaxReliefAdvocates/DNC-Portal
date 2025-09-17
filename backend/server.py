#!/usr/bin/env python3
"""
Server startup script for Do Not Call List Manager API
"""

import uvicorn
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from do_not_call.main import app
from do_not_call.config import settings


def main():
    """Main function to start the server"""
    # Get configuration from environment or use defaults
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "true").lower() == "true"
    # Normalize log level to what uvicorn expects (lowercase)
    log_level = os.getenv("LOG_LEVEL", "info").strip().lower()
    
    print(f"Starting Do Not Call List Manager API...")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Reload: {reload}")
    print(f"Log Level: {log_level}")
    print(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    print("-" * 50)
    
    # Start the server
    uvicorn.run(
        "do_not_call.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
        access_log=True,
    )


if __name__ == "__main__":
    main()





