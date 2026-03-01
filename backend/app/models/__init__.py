"""SQLAlchemy ORM models – imported here so Alembic autogenerate picks them up."""
from app.models.tenant import Tenant  # noqa: F401
from app.models.location import Location  # noqa: F401
from app.models.service import Service  # noqa: F401
from app.models.counter import Counter  # noqa: F401
from app.models.channel import Channel  # noqa: F401
from app.models.user import User, Role, UserRole  # noqa: F401
from app.models.ticket import Ticket  # noqa: F401
from app.models.ticket_event import TicketEvent  # noqa: F401
from app.models.interaction import Interaction  # noqa: F401
from app.models.idempotency_key import IdempotencyKey  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
