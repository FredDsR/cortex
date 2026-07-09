-- demo schema
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    balance DECIMAL(10,2) DEFAULT 0
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    account_id INTEGER REFERENCES accounts(id),
    total DECIMAL(10,2)
);
