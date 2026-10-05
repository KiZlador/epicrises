import os

from dotenv import load_dotenv
from waitress import serve

from backend.app import create_app
from domain.config import ROOT


def main():
    load_dotenv(ROOT / ".env")
    host, port = os.getenv("APP_HOST", "127.0.0.1"), int(os.getenv("APP_PORT", "5000"))
    print(f"Разбор эпикризов: http://{host}:{port}", flush=True)
    serve(create_app(), host=host, port=port, threads=8)


if __name__ == "__main__":
    main()
