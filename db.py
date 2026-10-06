from sqlalchemy import create_engine, String, Integer, Boolean, ForeignKey, DateTime, func, JSON
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Mapped, mapped_column
from .config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase): pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    picture: Mapped[str] = mapped_column(String(500), default="")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)   # only set directly in DB
    level_estimate: Mapped[str | None] = mapped_column(String(40), nullable=True)

class Level(Base):
    __tablename__ = "levels"
    slug: Mapped[str] = mapped_column(String(40), primary_key=True)
    title: Mapped[str] = mapped_column(String(80))
    position: Mapped[int] = mapped_column(Integer)
    price_cents: Mapped[int] = mapped_column(Integer, default=0)     # 0 => free
    currency: Mapped[str] = mapped_column(String(3), default="usd")
    lessons: Mapped[list] = mapped_column(JSON, default=list)

class Purchase(Base):
    __tablename__ = "purchases"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    level_slug: Mapped[str] = mapped_column(ForeignKey("levels.slug"))
    stripe_session_id: Mapped[str] = mapped_column(String(255), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|paid
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    created_at = mapped_column(DateTime, server_default=func.now())

SEED = [
    ("beginner", "Beginner", 1, 0),
    ("elementary", "Elementary", 2, 1500),
    ("intermediate", "Intermediate", 3, 2500),
    ("upper-intermediate", "Upper-Intermediate", 4, 3500),
    ("advanced", "Advanced", 5, 4500),
]

def init_db():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for slug, title, pos, price in SEED:
            if not db.get(Level, slug):
                db.add(Level(slug=slug, title=title, position=pos, price_cents=price,
                             lessons=[{"title": f"{title}: Lesson 1", "body": "Welcome!"}]))
        if settings.ADMIN_EMAIL and not db.query(User).filter_by(email=settings.ADMIN_EMAIL.lower()).first():
            db.add(User(email=settings.ADMIN_EMAIL.lower(), is_admin=True))
        db.commit()
