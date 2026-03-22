CREATE TABLE companies (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE,
    industry_id INT,
    shares_outstanding BIGINT,
    ADD CONSTRAINT fk_industry
        FOREIGN KEY (industry_id)
        REFERENCES industries(id);
);

CREATE TABLE exchanges (
    id SERIAL PRIMARY KEY,
    code TEXT UNIQUE
);

CREATE TABLE listings (
    id SERIAL PRIMARY KEY,
    company_id INT REFERENCES companies(id),
    exchange_id INT REFERENCES exchanges(id),
    ticker TEXT,
    UNIQUE (company_id, exchange_id)
);

CREATE TABLE stock_prices (
    listing_id INT REFERENCES listings(id),
    date DATE,
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
    volume BIGINT,
    PRIMARY KEY (listing_id, date)
);

CREATE INDEX idx_listing_date
ON stock_prices(listing_id, date);

CREATE TABLE sectors (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE industries (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    sector_id INT NOT NULL,
    CONSTRAINT fk_sector
        FOREIGN KEY(sector_id)
        REFERENCES sectors(id)
        ON DELETE CASCADE
);

-- Aggregated daily sentiment per sector (one row per sector per day)
CREATE TABLE sector_sentiment_daily (
    sector_id     INT  REFERENCES sectors(id),
    date          DATE NOT NULL,
    avg_score     NUMERIC NOT NULL,  -- weighted mean sentiment (-1 to +1)
    article_count INT,               -- how many articles were used
    PRIMARY KEY (sector_id, date)
);

-- Aggregated daily NSE Index Advance/Decline per sector (one row per sector per day)
CREATE TABLE sector_advance_decline_daily (
    sector_id     INT  REFERENCES sectors(id),
    date          DATE NOT NULL,
    advance       INT,
    decline       INT,
    unchanged     INT,
    total         INT,
    PRIMARY KEY (sector_id, date)
);
-- Model predictions per sector per day
CREATE TABLE sector_predictions (
    sector_id     INT  REFERENCES sectors(id),
    date          DATE NOT NULL,
    signal        TEXT NOT NULL,    -- 'UP' | 'DOWN' | 'NEUTRAL'
    confidence    NUMERIC,          -- model probability [0, 1]
    model_version TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (sector_id, date)
);