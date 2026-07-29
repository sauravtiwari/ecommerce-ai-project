"""FastAPI application entrypoint.

Start it with:  uvicorn app.main:app --reload
                        ^^^^^^^^ ^^^
                        module   variable

Read that argument as "import `app.main`, then find the variable named `app`
inside it". Uvicorn does not look for a magic filename -- you are handing it a
Python object by path.
"""

from fastapi import FastAPI

# This object IS the application: a routing table plus configuration.
# Creating it starts no server and opens no port.
app = FastAPI(
    title="E-Commerce AI API",
    version="0.1.0",
)


@app.get("/")
async def root() -> dict[str, str]:
    """The simplest possible endpoint.

    `async def` rather than `def` is deliberate, and Phase 3 is entirely about
    why. The one-line version for now: this function is a *coroutine*, so while
    it waits on something slow (a database, a network call) the server can run
    other requests instead of sitting idle. Here there is nothing to wait on,
    so it makes no practical difference yet -- but starting async avoids a
    painful refactor later.

    The returned dict is serialized to JSON automatically.
    """
    return {"service": "E-Commerce AI API", "status": "alive"}
