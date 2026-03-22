import os
from dotenv import load_dotenv


# Load variables from a local .env file in development.
load_dotenv()


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set. Add it to your environment or .env file.")
    return database_url
