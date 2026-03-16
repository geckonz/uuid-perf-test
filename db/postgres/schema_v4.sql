-- Schema for UUID v4 (random) benchmark
CREATE SCHEMA IF NOT EXISTS bench_v4;

CREATE TABLE IF NOT EXISTS bench_v4.customers (
    id          UUID        NOT NULL,
    name        VARCHAR(120),
    email       VARCHAR(254),
    phone       VARCHAR(30),
    address     TEXT,
    created_at  TIMESTAMPTZ,
    updated_at  TIMESTAMPTZ,
    CONSTRAINT customers_v4_pk PRIMARY KEY (id)
);

CREATE UNIQUE INDEX IF NOT EXISTS customers_v4_email_idx
    ON bench_v4.customers (email);

CREATE INDEX IF NOT EXISTS customers_v4_created_at_idx
    ON bench_v4.customers (created_at);

CREATE TABLE IF NOT EXISTS bench_v4.accounts (
    id              UUID            NOT NULL,
    customer_id     UUID            NOT NULL,
    account_type    VARCHAR(20),
    balance         NUMERIC(18, 2),
    currency        CHAR(3),
    status          VARCHAR(20),
    opened_at       TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ,
    CONSTRAINT accounts_v4_pk PRIMARY KEY (id),
    CONSTRAINT accounts_v4_customer_fk
        FOREIGN KEY (customer_id) REFERENCES bench_v4.customers (id)
);

CREATE INDEX IF NOT EXISTS accounts_v4_customer_id_idx
    ON bench_v4.accounts (customer_id);

CREATE INDEX IF NOT EXISTS accounts_v4_opened_at_idx
    ON bench_v4.accounts (opened_at);

CREATE INDEX IF NOT EXISTS accounts_v4_status_idx
    ON bench_v4.accounts (status);
