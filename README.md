# Mortgage Payoff

A consolidated rewrite of the original mortgage-payoff scripts using:

- Python for the month-by-month amortization calculation
- NumPy for reproducible random extra payments
- DuckDB for simulation storage and SQL analytics
- Matplotlib for the final payoff-distribution chart

Pandas and CSV round-trips are no longer part of the simulation path.

## Install

```bash
python -m pip install -e .
```

## Run

Equivalent to the original `payoff.py` defaults:

```bash
mortgage-payoff --fresh
```

Run a larger Monte Carlo experiment:

```bash
mortgage-payoff \
  --fresh \
  --simulations 100000 \
  --additional-min 0 \
  --additional-max 3500 \
  --seed 42
```

Store every monthly payment as well as the final result:

```bash
mortgage-payoff --fresh --simulations 100000 --store-payments
```

## Outputs

```text
mortgage.duckdb
output/
├── allruns.csv
├── payoff-results.csv
├── payoff-totals.csv
└── PayoffGraph.pdf
```

The DuckDB database is the primary analytical store. CSV files are exports for compatibility.

## DuckDB tables

### `payoff_results`

One row per simulation:

- `simulation_id`
- `payoff_date`
- `payoff_period`
- `end_balance`
- `total_additional_paid`
- `total_interest`

### `payments`

Optional monthly detail. It is populated when `--store-payments` is supplied.

## Useful SQL

```sql
SELECT *
FROM payoff_results
ORDER BY payoff_date;
```

Payoff-date distribution:

```sql
SELECT
    payoff_date,
    COUNT(*) AS simulations,
    COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () AS probability_pct
FROM payoff_results
GROUP BY payoff_date
ORDER BY payoff_date;
```

Average extra payment by payoff month:

```sql
SELECT
    payoff_date,
    AVG(total_additional_paid) AS avg_extra_paid,
    AVG(total_interest) AS avg_interest
FROM payoff_results
GROUP BY payoff_date
ORDER BY payoff_date;
```

## Design note

The amortization loop remains in Python because each month's calculation depends
on the previous month's balance. DuckDB is used where it is strongest: storing,
scanning, aggregating, and exporting batches of simulation results.

This also avoids the original workflow of building pandas DataFrames inside every
simulation, appending them to another DataFrame, writing CSV, reading that CSV
back into pandas, and then aggregating it.
