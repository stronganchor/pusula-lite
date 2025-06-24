# db.py
# Data layer (SQLAlchemy + SQLite) for Pusula-Lite

from __future__ import annotations

import pathlib
from contextlib import contextmanager

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Date,
    Numeric,
    ForeignKey,
    Text,
    text,  # for pragmatic migrations
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# ---------------------------------------------------------------------- #
#  Database location                                                     #
# ---------------------------------------------------------------------- #

DATA_DIR = pathlib.Path(__file__).with_name("data")
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "pusula.db"

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)

Base = declarative_base()


# ---------------------------------------------------------------------- #
#  ORM models                                                            #
# ---------------------------------------------------------------------- #

class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    phone = Column(String(30))
    address = Column(String(255))            # Ev adresi
    work_address = Column(String(255))       # İş adresi
    notes = Column(Text)

    contacts = relationship("Contact", back_populates="customer", cascade="all, delete")
    sales = relationship("Sale", back_populates="customer", cascade="all, delete")


class Contact(Base):
    """Alternate / delivery contact for a customer."""

    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"))
    name = Column(String(120))
    phone = Column(String(30))
    home_address = Column(String(255))       # Yeni
    work_address = Column(String(255))       # Yeni

    customer = relationship("Customer", back_populates="contacts")


class Sale(Base):
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"))
    total = Column(Numeric(10, 2), nullable=False)

    customer = relationship("Customer", back_populates="sales")
    installments = relationship(
        "Installment", back_populates="sale", cascade="all, delete"
    )


class Installment(Base):
    """A single scheduled payment belonging to a sale."""

    __tablename__ = "installments"

    id = Column(Integer, primary_key=True)
    sale_id = Column(Integer, ForeignKey("sales.id", ondelete="CASCADE"))
    due_date = Column(Date)
    amount = Column(Numeric(10, 2))
    paid = Column(Integer, default=0)  # 0 = not paid, 1 = paid

    sale = relationship("Sale", back_populates="installments")


# ---------------------------------------------------------------------- #
#  Helper functions                                                      #
# ---------------------------------------------------------------------- #

def _add_column_if_missing(conn, table: str, column: str, ddl: str) -> None:
    """Utility: add column if it is not yet in the table."""
    existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
    if column not in existing:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def init_db() -> None:
    """Create tables and apply lightweight migrations."""
    Base.metadata.create_all(engine)

    with engine.begin() as conn:
        # customers.work_address
        _add_column_if_missing(conn, "customers", "work_address", "VARCHAR(255)")
        # contacts.home_address + contacts.work_address
        _add_column_if_missing(conn, "contacts", "home_address", "VARCHAR(255)")
        _add_column_if_missing(conn, "contacts", "work_address", "VARCHAR(255)")


@contextmanager
def session():
    """Provide a transactional scope around a series of operations."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
