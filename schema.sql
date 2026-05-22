-- schema.sql
-- Relational schema for the Lucknow Artisan Credit Scoring System.
-- All tables use INTEGER PRIMARY KEY AUTOINCREMENT for SQLite rowid aliasing.

CREATE TABLE IF NOT EXISTS artisans (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT    NOT NULL,
    cluster             TEXT    NOT NULL CHECK(cluster IN ('Chowk', 'Aminabad')),
    craft_type          TEXT    NOT NULL CHECK(craft_type IN ('Chikankari', 'Zardozi')),
    artisan_card_number TEXT    UNIQUE,
    artisan_card_status TEXT    NOT NULL DEFAULT 'Unregistered'
                                CHECK(artisan_card_status IN ('Active', 'Pending', 'Unregistered')),
    phone               TEXT,
    years_active        INTEGER NOT NULL DEFAULT 1 CHECK(years_active >= 1),
    annual_turnover     REAL    NOT NULL DEFAULT 0.0 CHECK(annual_turnover >= 0),
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- B2B GST invoice history.  overdue_days tracks total days payment was delayed
-- (0 = settled on invoice date; >90 = severe default signal).
CREATE TABLE IF NOT EXISTS gst_invoices (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    artisan_id     INTEGER NOT NULL,
    invoice_number TEXT    NOT NULL UNIQUE,
    invoice_date   DATE    NOT NULL,
    buyer_name     TEXT    NOT NULL,
    invoice_value  REAL    NOT NULL CHECK(invoice_value > 0),
    tax_paid       REAL    NOT NULL DEFAULT 0.0 CHECK(tax_paid >= 0),
    payment_status TEXT    NOT NULL CHECK(payment_status IN ('Paid', 'Pending', 'Overdue')),
    overdue_days   INTEGER NOT NULL DEFAULT 0 CHECK(overdue_days >= 0),
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (artisan_id) REFERENCES artisans(id) ON DELETE CASCADE
);

-- Informal order ledger: captures buyer relationships and settlement timing
-- that don't appear in formal GST records (cash sales, advance bookings, etc.).
CREATE TABLE IF NOT EXISTS order_ledgers (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    artisan_id          INTEGER NOT NULL,
    buyer_name          TEXT    NOT NULL,
    order_date          DATE    NOT NULL,
    delivery_date       DATE,
    settlement_date     DATE,
    order_value         REAL    NOT NULL CHECK(order_value > 0),
    settlement_time_days INTEGER CHECK(settlement_time_days >= 0),
    is_repeat_buyer     INTEGER NOT NULL DEFAULT 0 CHECK(is_repeat_buyer IN (0, 1)),
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (artisan_id) REFERENCES artisans(id) ON DELETE CASCADE
);

-- Government scheme eligibility criteria.
-- NULL max_annual_turnover means no upper cap exists for that scheme.
CREATE TABLE IF NOT EXISTS govt_schemes (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_name          TEXT NOT NULL UNIQUE,
    scheme_category      TEXT NOT NULL,
    min_annual_turnover  REAL NOT NULL DEFAULT 0.0,
    max_annual_turnover  REAL,
    min_loan_amount      REAL NOT NULL,
    max_loan_amount      REAL NOT NULL,
    requires_artisan_card INTEGER NOT NULL DEFAULT 0 CHECK(requires_artisan_card IN (0, 1)),
    min_years_active     INTEGER NOT NULL DEFAULT 0,
    min_credit_score     INTEGER NOT NULL DEFAULT 300,
    description          TEXT,
    eligibility_notes    TEXT
);

CREATE INDEX IF NOT EXISTS idx_gst_artisan  ON gst_invoices(artisan_id);
CREATE INDEX IF NOT EXISTS idx_gst_date     ON gst_invoices(invoice_date);
CREATE INDEX IF NOT EXISTS idx_ledger_artisan ON order_ledgers(artisan_id);
CREATE INDEX IF NOT EXISTS idx_ledger_buyer   ON order_ledgers(buyer_name);
