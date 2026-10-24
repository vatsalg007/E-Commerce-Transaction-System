from sqlalchemy import text

from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    result = db.session.execute(
        text("DELETE FROM idempotency_keys WHERE created_at < now() - interval '24 hours'")
    )
    db.session.commit()
    print(f"Deleted {result.rowcount} expired idempotency keys.")