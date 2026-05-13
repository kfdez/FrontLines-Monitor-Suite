"""Web service entrypoint for Ubuntu deployments."""
import os

import uvicorn


def main():
    host = os.environ.get("FRONTLINES_HOST", "127.0.0.1")
    port = int(os.environ.get("FRONTLINES_PORT", "8000"))
    uvicorn.run("server.app:app", host=host, port=port)


if __name__ == "__main__":
    main()
