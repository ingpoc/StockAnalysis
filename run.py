import sys
import os
import uvicorn
try:
    import uvloop
    uvloop.install()
except ImportError:
    pass

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    # Use all available CPU cores for workers
    workers = os.cpu_count() or 1
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        reload_dirs=["src"],
        workers=workers
    ) 