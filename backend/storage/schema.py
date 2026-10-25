from sqlalchemy import Column, ForeignKey, Index, Integer, MetaData, String, Table, text

metadata = MetaData()

members = Table(
    "members",
    metadata,
    Column("user_id", String(30), primary_key=True),
    Column("display_name", String(50), nullable=False),
)

sessions = Table(
    "sessions",
    metadata,
    Column("token_hash", String(64), primary_key=True),
    Column("user_id", String(30), ForeignKey("members.user_id"), nullable=False),
    # Unix seconds: SQLite has no timezone-aware datetime type.
    Column("expires_at", Integer, nullable=False),
)

groups = Table(
    "groups",
    metadata,
    Column("group_id", Integer, primary_key=True),
    Column("name", String(60), nullable=False),
    Column("name_key", String(60), nullable=False, unique=True),
    Column("description", String(200), nullable=False),
    Column("owner_id", String(30), ForeignKey("members.user_id"), nullable=False, index=True),
)

memberships = Table(
    "memberships",
    metadata,
    Column("group_id", Integer, ForeignKey("groups.group_id"), primary_key=True),
    Column("user_id", String(30), ForeignKey("members.user_id"), primary_key=True, index=True),
)

join_requests = Table(
    "join_requests",
    metadata,
    Column("request_id", Integer, primary_key=True),
    Column("group_id", Integer, ForeignKey("groups.group_id"), nullable=False),
    Column("user_id", String(30), ForeignKey("members.user_id"), nullable=False, index=True),
    Column("status", String(10), nullable=False),
)

# At most one pending request per member and group; decided requests are kept as history.
Index(
    "one_pending_request",
    join_requests.c.group_id,
    join_requests.c.user_id,
    unique=True,
    sqlite_where=text("status = 'pending'"),
)
