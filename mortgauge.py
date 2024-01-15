from moneyed import Money, GBP
import pandas as pd 
from tabulate import tabulate
from decimal import Decimal

# https://en.wikipedia.org/wiki/Amortizing_loan
def amortize(principal, rate, total_payment_count):
    P=principal
    i=rate/12
    n=total_payment_count
    num=P*i*((1+i)**n)
    den=((1+i)**n)-1
    return num/den

class Mortgage:
    def __init__(self, principal, rate, term, fixed_period=0, fee=0, smr=None):
        self.principal=principal
        self.rate=rate
        self.term=term
        self.fee=fee
        self.smr=smr if smr else rate
        self.total_payment_count=12*self.term
        self.fixed_payment=amortize(self.principal, self.rate, self.total_payment_count)
        self.current_payment_number=0
        self.balance=principal
        self.fixed_period=fixed_period
    
    def get_fee(self):
        return self.fee

    def get_smr(self):
        return self.smr

    def get_balance(self):
        return self.balance
    
    def get_current_payment_number(self):
        return self.current_payment_number

    def get_term(self):
        return self.term

    def get_rate(self):
        return self.rate

    def get_principal(self):
        return self.principal

    def get_fixed_payment(self):
        return self.fixed_payment

    def get_total_payment_count(self):
        return self.total_payment_count

    def get_fixed_period(self):
        return self.fixed_period


class InterestForecast:
    def __init__(self, term):
        self.term=term
        self.total_payment_count=12*self.term
        self.data={n: None for n in range(1, self.total_payment_count+1)}

    def add_data_point(self, payment, value):
        self.data[payment]=value

    def finalize(self):
        self.series=pd.Series(data=self.data).interpolate()

    def get_value(self, payment):
        return self.series[payment]

    def to_series(self):
        return self.series

class OverpaymentSchedule:
    def __init__(self, term):
        self.term=term
        self.total_payment_count=12*self.term
        self.data={n: None for n in range(1, self.total_payment_count+1)}

    def add_data_point(self, payment, value):
        self.data[payment]=value

    def finalize(self):
        # Convert data to float as pandas cannnot interpolate Money 
        float_data={x: float(self.data[x].amount) if self.data[x] is not None else None for x in self.data }
        intermediate=pd.Series(data=float_data).interpolate()
        self.series=intermediate.apply(lambda x: Money(x, GBP) if x is not None else None)

    def get_value(self, payment):
        return self.series[payment]

    def to_series(self):
        return self.series

class MortgageSummary:
    def __init__(self,data):
        self.data=data

class MortgageSimulator:
    def __init__(self):
        self.rate_forecast=None
        self.overpayment_schedule=None
    
    def set_rate_forecast(self, rate_forecast):
        self.rate_forecast=rate_forecast

    def set_overpayment_schedule(self, overpayment_schedule):
        self.overpayment_schedule=overpayment_schedule
    
    def __get_rate(self, payment, mortgage):
        fixed_period=mortgage.get_fixed_period()
        rate=None
        if payment <= fixed_period*12:
            rate=mortgage.get_rate()
        elif payment>fixed_period*12 and self.rate_forecast:
            rate=self.rate_forecast.get_value(payment)
        else:
            rate=mortgage.get_smr()
        return rate

    def run(self, mortgage):
        """
        Run the simulation
        """
        # Generate data in primitive form. Growing a dataframe is bad practice
        data=[]
        payment=1
        # We use Money.amount as a balance that shows £0.00 is not necessarily equal to Money(0, GBP)
        while mortgage.balance.amount > 0.004 and payment < mortgage.get_total_payment_count()+1:
            # Set defaults
            scheduled_monthly_payment=Money(0,GBP)
            total_monthly_payment=Money(0,GBP)
            overpayment=Money(0,GBP)
            interest_payment=Money(0,GBP)
            scheduled_principal_payment=Money(0,GBP)
            total_principal_payment=Money(0,GBP)

            # Aliases
            fixed_period=mortgage.get_fixed_period()
            balance=mortgage.get_balance()
            rate=self.__get_rate(payment, mortgage)

            # Determine calculated variables
            interest_payment=rate*balance/12
            if payment <= fixed_period*12:
                scheduled_monthly_payment=mortgage.get_fixed_payment()
            else:
                remaining_payments=mortgage.get_total_payment_count() - payment +1 # include current payment
                scheduled_monthly_payment=amortize(balance, rate, remaining_payments)
            scheduled_principal_payment=scheduled_monthly_payment-interest_payment
            if self.overpayment_schedule:
                overpayment=self.overpayment_schedule.get_value(payment)
            total_principal_payment=scheduled_principal_payment+overpayment

            # Special case - final payment. There's certainly an easier way to do this
            if total_principal_payment>balance:
                if scheduled_principal_payment > balance:
                    scheduled_principal_payment=balance
                    overpayment=Money(0, GBP)
                else:
                    overpayment=balance-scheduled_principal_payment
                scheduled_monthly_payment=scheduled_principal_payment+interest_payment
                total_principal_payment=balance
            total_monthly_payment=scheduled_monthly_payment+overpayment

            # update loop variables
            mortgage.balance -= total_principal_payment

            # add row to data
            balance=mortgage.get_balance()
            data.append([payment, balance, rate, total_monthly_payment, interest_payment, scheduled_principal_payment, overpayment])
            payment+=1
        self.__analyse_full_term(mortgage, data)
        self.__print_analysis()

    def __analyse_full_term(self, mortgage, data):
        analysis=MortgageSummary("a")
        df = pd.DataFrame(data, columns=['payment', 'balance', 'rate', 'monthly', 'interest', 'principal', 'overpayment'])
        df['cum_interest'] = df['interest'].cumsum()
        df['cum_principal'] = df['principal'].cumsum()
        df['cum_overpayment'] = df.overpayment.cumsum()
        total_interest=df['cum_interest'].iloc[-1]
        total_principal=mortgage.get_principal()
        df['cum_int_percent'] = df.cum_interest*100/total_interest
        df['cum_principal_percent'] = (df.cum_principal+df.cum_overpayment)*100/total_principal
        analysis.total_interest=total_interest
        analysis.payments=df
        analysis.fixed_term_cost=df.cum_interest.iloc[mortgage.get_fixed_period()*12]
        # analysis.aprc=(total_interest+mortgage.get_fee())*100/(mortgage.get_principal()*mortgage.get_term())
        # print(analysis.aprc)
        self.df=df

    def __print_analysis(self):
        print(tabulate(self.df, headers='keys', tablefmt='psql', showindex=False))

MORTGAGE_TERM_YEARS=25
MORTGAGE_LOAN_AMOUNT_GBP=500000
MORTGAGE_RATE=0.05
MORTGAGE_SMR=0.07
MORTGAGE_FEE_GBP=999

rate_forecast=InterestForecast(MORTGAGE_TERM_YEARS)
rate_forecast.add_data_point(1, 0.06)
rate_forecast.add_data_point(24, 0.05)
rate_forecast.add_data_point(100, 0.05)
rate_forecast.add_data_point(300, 0.05)
rate_forecast.finalize()

overpayment_schedule=OverpaymentSchedule(MORTGAGE_TERM_YEARS)
overpayment_schedule.add_data_point(1, Money(500, GBP))
overpayment_schedule.add_data_point(300, Money(500, GBP))
overpayment_schedule.finalize()

x=Mortgage(  Money(MORTGAGE_LOAN_AMOUNT_GBP, GBP),
             MORTGAGE_RATE, 
             MORTGAGE_TERM_YEARS, 
             fixed_period=1,
             fee=Money(MORTGAGE_FEE_GBP, GBP),
             smr=MORTGAGE_SMR)

sim=MortgageSimulator()
# sim.set_rate_forecast(rate_forecast)
sim.set_overpayment_schedule(overpayment_schedule)
sim.run(x)
