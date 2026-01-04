import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

PG_DSN = os.getenv("PG_DSN")

def get_conn():
    return psycopg.connect(PG_DSN)
