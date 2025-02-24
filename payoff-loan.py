import pandas as pd
import numpy as np
import numpy_financial as npf
from datetime import date as dt

def create_single_run_df(start_date, years, payments_year, interest, mortgage):
    rng = pd.date_range(start_date, periods=years * payments_year, freq='MS')
    df = pd.DataFrame(index=rng, columns=['orig_total_payment', 'total_payment', 'interest', 'principal', 'additional_payment', 'orig_end_balance', 'end_balance'], dtype='float')
    df.reset_index(inplace=True)
    df.index += 1
    df.index.name = "period"
    df.rename(columns={'index': 'payment_date'}, inplace=True)
    df['payment_date'] = pd.to_datetime(df['payment_date']).dt.strftime('%m-%Y')
    
    initial_pmt = 500
    initial_ipmt = -1 * npf.ipmt(interest / payments_year, 1, years * payments_year, mortgage)
    initial_ppmt = -1 * npf.ppmt(interest / payments_year, 1, years * payments_year, mortgage)
    additional_pmt = np.random.randint(0, 600, size=len(df))
    
    initial_row_dict = {
        'orig_total_payment': initial_pmt,
        'total_payment': initial_pmt + additional_pmt[0],
        'interest': initial_ipmt,
        'principal': initial_ppmt,
        'additional_payment': additional_pmt[0],
        'orig_end_balance': mortgage - initial_ppmt,
        'end_balance': mortgage - initial_ppmt - additional_pmt[0]
    }
    df.loc[1, list(initial_row_dict.keys())] = list(initial_row_dict.values())
    
    for period in range(2, len(df) + 1):
        previous_orig_end_balance = df.loc[period - 1, 'orig_end_balance']
        period_interest = previous_orig_end_balance * interest / payments_year
        period_principal = initial_pmt - period_interest
        additional_pmt = np.random.randint(0, 600)
        orig_end_balance = previous_orig_end_balance - period_principal
        end_balance = df.loc[period - 1, 'end_balance'] - period_principal - additional_pmt
        
        row_dict = {
            'orig_total_payment': initial_pmt,
            'total_payment': initial_pmt + additional_pmt,
            'interest': period_interest,
            'principal': period_principal,
            'additional_payment': additional_pmt,
            'orig_end_balance': orig_end_balance,
            'end_balance': end_balance
        }
        df.loc[period, list(row_dict.keys())] = list(row_dict.values())

    return df[df['end_balance'] >= 1000].round(2).tail(1)

def main():
    storage_df = pd.DataFrame()
    num_runs = 10
    start_date = dt(2025, 7, 1)
    years = 10
    payments_year = 12
    interest = 0.0508
    mortgage = 21000
    
    for _ in range(num_runs):
        last_row = create_single_run_df(start_date, years, payments_year, interest, mortgage)
        storage_df = pd.concat([storage_df, last_row], ignore_index=True)
    
    finaldf = storage_df[["payment_date", 'end_balance']]
    # finaldf.to_csv('allruns.csv', index=False)
    
    df2 = finaldf['payment_date'].value_counts()
    df2 = df2.reset_index()
    df2.columns = ['payment_date', 'count']
    df2.to_csv('payoff-totals.csv', index=False)

    print("All runs have been completed and saved to CSV files.")

if __name__ == "__main__":
    main()
