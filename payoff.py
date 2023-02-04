import pandas as pd
import numpy as np
import numpy_financial as npf
from datetime import date, datetime
from numpy import random

interest=0.04125
years=2
payments_year=12
mortgage=40000
start_date=(date(2023, 2, 1))

initial_pmt = -1 * npf.pmt(interest/12, years*payments_year, mortgage)
initial_ipmt = -1 * npf.ipmt(interest/payments_year, 1, years*payments_year, mortgage)
initial_ppmt = -1 * npf.ppmt(interest/payments_year, 1, years*payments_year, mortgage)
print('Initial Payment: {:,.2f}'.format(initial_pmt))
print('Initial Interest: {:,.2f}'.format(initial_ipmt))
print('Initial Principal Payment: {:,.2f}'.format(initial_ppmt))

# Create date range in pandas dataframe
rng = pd.date_range(start_date, periods=years * payments_year, freq='MS')


# label the date column
rng.name="Payment Date"

# create dataframe
df=pd.DataFrame(
    index=rng,
    columns= ['Org Total Payment',
              'Total Payment',
              'Interest',
              'Principal',
              'Additional Payment',
              'Org Ending Balance',
              'Ending Balance'], dtype='float')

# set index as payment period
df.reset_index(inplace=True)
df.index += 1
df.index.name="Period"

initial_additional_pmt= extra_payment
random = [random.randint(2100,4000) for k in df.index]

# Create values for the first period
period=1

# for each element in the row set the value
initial_row_dict = {
    'Org Total Payment':initial_pmt,
    'Total Payment': initial_pmt + (initial_additional_pmt),
    'Interest': initial_ipmt,
    'Principal':initial_ppmt,
    'Additional Payment': initial_additional_pmt,
    'Org Ending Balance': mortgage - initial_ppmt,
    'Ending Balance': mortgage - initial_ppmt - (initial_additional_pmt)
}

# set values
columns = list(initial_row_dict.keys())
period_values = list(initial_row_dict.values())
df.at[period, columns]= period_values

# round values
df = df.round(2)
df

# add additional rows
for period in range(2, len(df) + 1):
    #get prior period values
    previous_total_payment = df.loc[period - 1, 'Total Payment']
    previous_principal = df.loc[period - 1, 'Principal']
    previous_org_ending_balance = df.loc[period - 1, 'Org Ending Balance']
    previous_ending_balance = df.loc[period - 1, 'Ending Balance']
    period_additional_payment = random
    #get end balance
    period_interest = previous_org_ending_balance * interest / payments_year
    period_principal = initial_pmt - period_interest
    org_ending_balance = previous_org_ending_balance - period_principal
    ending_balance = previous_ending_balance - period_principal - period_additional_payment
    #org_ending_balance = 0 if org_ending_balance < 0 else org_ending_balance
    #ending_balance = 0 if ending_balance < 0 else ending_balance
    #org_ending_balance = np.logical_or (org_ending_balance < 0,
    #                                    org_ending_balance)
    #ending_balance = np.logical_or (ending_balance < 0,ending_balance)

    row_dict = {'Org Total Payment':initial_pmt,
                'Total Payment': initial_pmt + (period_additional_payment),
                'Interest': period_interest,
                'Principal': period_principal,
                'Additional Payment': period_additional_payment,
                'Org Ending Balance': org_ending_balance,
                'Ending Balance': ending_balance}
    columns = list(row_dict.keys())
    period_values = list(row_dict.values())
    df.at[period, columns]= period_values

df.to_csv('amort.csv')