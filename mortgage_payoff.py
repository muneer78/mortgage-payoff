#!/usr/bin/env python3
"""Monte Carlo mortgage-payoff simulator backed by DuckDB.

The amortization calculation is deliberately kept in Python: each simulation
depends on the previous month's balance. DuckDB is used for durable storage,
aggregation, and analytical queries, avoiding pandas and CSV round-trips.
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import numpy as np


@dataclass(frozen=True)
class Mortgage:
    mortgage: float
    annual_rate: float
    years: int
    payments_per_year: int
    scheduled_payment: float
    start_date: date


def month_add(d: date, months: int) -> date:
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    return date(year, month, 1)


def amortize(
    mortgage: Mortgage,
    rng: np.random.Generator,
    simulation_id: int,
    additional_min: int,
    additional_max: int,
    stop_balance: float,
):
    """Yield one row per month until the requested stop balance is reached."""
    balance = mortgage.mortgage
    original_balance = mortgage.mortgage
    monthly_rate = mortgage.annual_rate / mortgage.payments_per_year
    n_periods = mortgage.years * mortgage.payments_per_year

    for period in range(1, n_periods + 1):
        payment_date = month_add(mortgage.start_date, period - 1)

        if period == 1:
            interest = original_balance * monthly_rate
            principal = mortgage.scheduled_payment - interest
            additional = int(rng.integers(additional_min, additional_max + 1))
        else:
            interest = original_balance * monthly_rate
            principal = mortgage.scheduled_payment - interest
            additional = int(rng.integers(additional_min, additional_max + 1))

        original_balance = max(0.0, original_balance - principal)
        balance = max(0.0, balance - principal - additional)

        yield (
            simulation_id,
            period,
            payment_date,
            mortgage.scheduled_payment,
            mortgage.scheduled_payment + additional,
            interest,
            principal,
            additional,
            original_balance,
            balance,
        )

        if balance < stop_balance or original_balance <= 0:
            break


SCHEMA = """
CREATE TABLE IF NOT EXISTS payments (
    simulation_id BIGINT,
    period INTEGER,
    payment_date DATE,
    scheduled_payment DOUBLE,
    total_payment DOUBLE,
    interest DOUBLE,
    principal DOUBLE,
    additional_payment DOUBLE,
    original_end_balance DOUBLE,
    end_balance DOUBLE
);

CREATE TABLE IF NOT EXISTS payoff_results (
    simulation_id BIGINT PRIMARY KEY,
    payoff_date DATE,
    payoff_period INTEGER,
    end_balance DOUBLE,
    total_additional_paid DOUBLE,
    total_interest DOUBLE
);
"""


def create_database(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(SCHEMA)


def run_simulations(
    con: duckdb.DuckDBPyConnection,
    mortgage: Mortgage,
    simulations: int,
    additional_min: int,
    additional_max: int,
    stop_balance: float,
    seed: int,
    store_payments: bool,
    batch_size: int = 10_000,
) -> None:
    rng = np.random.default_rng(seed)
    payment_rows = []
    payoff_rows = []

    for simulation_id in range(1, simulations + 1):
        rows = list(
            amortize(
                mortgage,
                rng,
                simulation_id,
                additional_min,
                additional_max,
                stop_balance,
            )
        )

        last = rows[-1]
        total_additional = sum(row[7] for row in rows)
        total_interest = sum(row[5] for row in rows)

        payoff_rows.append(
            (
                simulation_id,
                last[2],
                last[1],
                last[9],
                total_additional,
                total_interest,
            )
        )

        if store_payments:
            payment_rows.extend(rows)
            if len(payment_rows) >= batch_size:
                con.executemany(
                    """INSERT INTO payments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    payment_rows,
                )
                payment_rows.clear()

        if simulation_id % 1000 == 0:
            print(f"Completed {simulation_id:,}/{simulations:,} simulations")

    if payment_rows:
        con.executemany(
            """INSERT INTO payments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            payment_rows,
        )

    con.executemany(
        """INSERT INTO payoff_results VALUES (?, ?, ?, ?, ?, ?)""",
        payoff_rows,
    )


def export_results(con: duckdb.DuckDBPyConnection, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    con.execute(
        f"""
        COPY (
            SELECT payoff_date AS payment_date,
                   end_balance
            FROM payoff_results
            ORDER BY simulation_id
        ) TO '{(output_dir / "allruns.csv").as_posix()}'
        (HEADER, DELIMITER ',')
        """
    )

    con.execute(
        f"""
        COPY (
            SELECT
                payoff_date AS payment_date,
                COUNT(*) AS count,
                ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS probability_pct,
                ROUND(AVG(end_balance), 2) AS avg_remaining_balance
            FROM payoff_results
            GROUP BY payoff_date
            ORDER BY payoff_date
        ) TO '{(output_dir / "payoff-totals.csv").as_posix()}'
        (HEADER, DELIMITER ',')
        """
    )

    con.execute(
        f"""
        COPY (
            SELECT
                simulation_id,
                payoff_date,
                payoff_period,
                ROUND(end_balance, 2) AS end_balance,
                ROUND(total_additional_paid, 2) AS total_additional_paid,
                ROUND(total_interest, 2) AS total_interest
            FROM payoff_results
            ORDER BY simulation_id
        ) TO '{(output_dir / "payoff-results.csv").as_posix()}'
        (HEADER, DELIMITER ',')
        """
    )


def print_summary(con: duckdb.DuckDBPyConnection) -> None:
    row = con.execute(
        """
        SELECT
            COUNT(*) AS simulations,
            MIN(payoff_date) AS earliest_payoff,
            MAX(payoff_date) AS latest_payoff,
            ROUND(AVG(payoff_period), 1) AS avg_period,
            ROUND(AVG(total_additional_paid), 2) AS avg_additional,
            ROUND(AVG(total_interest), 2) AS avg_interest
        FROM payoff_results
        """
    ).fetchone()

    print("\nSimulation summary")
    print("------------------")
    print(f"Simulations:             {row[0]:,}")
    print(f"Earliest payoff:         {row[1]}")
    print(f"Latest payoff:           {row[2]}")
    print(f"Average payoff period:   {row[3]} months")
    print(f"Average extra paid:      ${row[4]:,.2f}")
    print(f"Average interest:        ${row[5]:,.2f}")


def make_chart(con: duckdb.DuckDBPyConnection, output_dir: Path) -> None:
    data = con.execute(
        """
        SELECT payoff_date, COUNT(*) AS simulations
        FROM payoff_results
        GROUP BY payoff_date
        ORDER BY payoff_date
        """
    ).fetchall()

    if not data:
        return

    dates = [row[0] for row in data]
    counts = [row[1] for row in data]

    plt.figure(figsize=(10, 6))
    plt.bar(dates, counts)
    plt.xticks(rotation=45, ha="right")
    plt.xlabel("Payoff date")
    plt.ylabel("Simulations")
    plt.title("Mortgage Payoff Distribution")
    plt.tight_layout()
    plt.savefig(output_dir / "PayoffGraph.pdf")
    plt.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mortgage", type=float, default=26239.82)
    parser.add_argument("--rate", type=float, default=0.04125)
    parser.add_argument("--years", type=int, default=1)
    parser.add_argument("--payments-per-year", type=int, default=12)
    parser.add_argument("--payment", type=float, default=965.99)
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2023, 5, 1))
    parser.add_argument("--simulations", type=int, default=1000)
    parser.add_argument("--additional-min", type=int, default=0)
    parser.add_argument("--additional-max", type=int, default=3500)
    parser.add_argument("--stop-balance", type=float, default=15000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--database", type=Path, default=Path("mortgage.duckdb"))
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument(
        "--store-payments",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Store every monthly payment row in DuckDB. Default: only final simulation results.",
    )
    parser.add_argument("--fresh", action="store_true", help="Delete the existing DuckDB database first.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.simulations < 1:
        raise SystemExit("--simulations must be >= 1")
    if args.additional_min < 0 or args.additional_max < args.additional_min:
        raise SystemExit("Invalid additional-payment range")

    if args.fresh and args.database.exists():
        args.database.unlink()

    mortgage = Mortgage(
        mortgage=args.mortgage,
        annual_rate=args.rate,
        years=args.years,
        payments_per_year=args.payments_per_year,
        scheduled_payment=args.payment,
        start_date=args.start_date,
    )

    con = duckdb.connect(str(args.database))
    try:
        create_database(con)

        # A rerun with the same database should be explicit rather than
        # silently mixing simulations from different parameter sets.
        con.execute("DELETE FROM payoff_results")
        con.execute("DELETE FROM payments")

        run_simulations(
            con,
            mortgage,
            args.simulations,
            args.additional_min,
            args.additional_max,
            args.stop_balance,
            args.seed,
            args.store_payments,
        )

        export_results(con, args.output_dir)
        print_summary(con)
        make_chart(con, args.output_dir)
        print(f"\nDuckDB database: {args.database}")
        print(f"Results:          {args.output_dir}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
