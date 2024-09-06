import pandas as pd
import numpy as np
import numpy_financial as npf
from datetime import date
import matplotlib.pyplot as plt

def create_single_run_df(start_date, years, payments_year, interest, mortgage):
    rng = pd.date_range(start_date, periods=years * payments_year, freq='MS')
    df = pd.DataFrame(index=rng, columns=['Org Total Payment', 'Total Payment', 'Interest', 'Principal', 'Additional Payment', 'Org Ending Balance', 'Ending Balance'], dtype='float')
    df.reset_index(inplace=True)
    df.index += 1
    df.index.name = "Period"
    df['Payment Date'] = df['Payment Date'].dt.strftime('%m-%Y')
    
    initial_pmt = 965.99
    initial_ipmt = -1 * npf.ipmt(interest / payments_year, 1, years * payments_year, mortgage)
    initial_ppmt = -1 * npf.ppmt(interest / payments_year, 1, years * payments_year, mortgage)
    additional_pmt = np.random.randint(0, 3500, size=len(df))
    
    initial_row_dict = {
        'Org Total Payment': initial_pmt,
        'Total Payment': initial_pmt + additional_pmt,
        'Interest': initial_ipmt,
        'Principal': initial_ppmt,
        'Additional Payment': additional_pmt,
        'Org Ending Balance': mortgage - initial_ppmt,
        'Ending Balance': mortgage - initial_ppmt - additional_pmt
    }
    columns = list(initial_row_dict.keys())
    period_values = list(initial_row_dict.values())
    df.at[1, columns] = period_values
    
    for period in range(2, len(df) + 1):
        previous_org_ending_balance = df.loc[period - 1, 'Org Ending Balance']
        period_interest = previous_org_ending_balance * interest / payments_year
        period_principal = initial_pmt - period_interest
        additional_pmt = np.random.randint(1000, 3500) + 400
        org_ending_balance = previous_org_ending_balance - period_principal
        ending_balance = df.loc[period - 1, 'Ending Balance'] - period_principal - additional_pmt
        
        row_dict = {
            'Org Total Payment': initial_pmt,
            'Total Payment': initial_pmt + additional_pmt,
            'Interest': period_interest,
            'Principal': period_principal,
            'Additional Payment': additional_pmt,
            'Org Ending Balance': org_ending_balance,
            'Ending Balance': ending_balance
        }
        columns = list(row_dict.keys())
        period_values = list(row_dict.values())
        df.at[period, columns] = period_values
    
    return df[df['Ending Balance'] >= 15000].round(2).tail(1)

def main():
    storage_df = pd.DataFrame()
    num_runs = 1000
    start_date = date(2023, 4, 1)
    years = 1
    payments_year = 12
    interest = 0.04125
    mortgage = 35763.56
    
    for _ in range(num_runs):
        last_row = create_single_run_df(start_date, years, payments_year, interest, mortgage)
        storage_df = storage_df.append(last_row, ignore_index=True)
    
    finaldf = storage_df[["Payment Date", 'Ending Balance']]
    finaldf.to_csv('allruns.csv', index=False)
    
    df = pd.read_csv('allruns.csv')
    df2 = df['Payment Date'].value_counts()
    df2.to_csv('payofftotals.csv', index=False)
    
    plt.figure()
    plt.xticks(rotation=180)
    df2.plot.bar(x='Payment Date', y='val')
    plt.tight_layout()
    plt.savefig('PayoffGraph.pdf')

if __name__ == "__main__":
    main()
