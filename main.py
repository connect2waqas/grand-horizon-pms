"""
main.py - Entry point and proxy for api/index.py
Allows local execution with `uvicorn main:app --port 8000` as well as
`uvicorn api.index:app --port 8000`, and ensures test suite continuity.
"""

from api.index import app, get_db

__all__ = ["app", "get_db"]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.index:app", host="127.0.0.1", port=8000, reload=True)
