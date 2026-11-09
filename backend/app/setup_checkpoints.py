# Initialize the PostgreSQL tables used by LangGraph checkpoints.
"""Initialize the LangGraph PostgreSQL checkpoint tables once."""
from langgraph.checkpoint.postgres import PostgresSaver
from sqlalchemy.engine import make_url
from backend.app.config import get_settings

if __name__ == "__main__":
    url = make_url(get_settings().database_url).set(drivername="postgresql")
    with PostgresSaver.from_conn_string(url.render_as_string(hide_password=False)) as saver:
        saver.setup()
    print("Investigation checkpoint tables are ready.")
