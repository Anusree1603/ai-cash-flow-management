import pandas as pd
from django.db.models import Sum
from forecast_app.models import Transaction

def get_daily_cashflow_df(user):
    """
    Returns daily net cash flow. 
    Useful for detailed historical tracking.
    """
    income_qs = (
        Transaction.objects
        .filter(user=user, transaction_type="income")
        .values("date")
        .annotate(total_income=Sum("amount"))
    )

    expense_qs = ( 
        Transaction.objects
        .filter(user=user, transaction_type="expense")
        .values("date")
        .annotate(total_expense=Sum("amount"))
    )

    income_df = pd.DataFrame(list(income_qs))
    expense_df = pd.DataFrame(list(expense_qs))

    if income_df.empty:
        income_df = pd.DataFrame(columns=["date", "total_income"])
    if expense_df.empty:
        expense_df = pd.DataFrame(columns=["date", "total_expense"])

    df = pd.merge(income_df, expense_df, on="date", how="outer").fillna(0)
    df["y"] = df["total_income"] - df["total_expense"]

    df = df.rename(columns={"date": "ds"})
    df["ds"] = pd.to_datetime(df["ds"])

    return df[["ds", "y"]].sort_values("ds")


def get_monthly_cashflow_df(user):
    """
    Monthly cash flow split by type (Income vs Expense).
    Optimized for the Double Prophet model to predict math: Income - Expense.
    """
    # 1. Fetch grouped data from Database
    qs = (
        Transaction.objects
        .filter(user=user)
        .values("date__year", "date__month", "transaction_type")
        .annotate(total=Sum("amount"))
    )

    df = pd.DataFrame(list(qs))

    # 2. Handle empty database state
    if df.empty:
        return pd.DataFrame(columns=["ds", "income", "expense"])

    
    #3 This turns 'transaction_type' rows into 'income' and 'expense' columns
    pivot_df = df.pivot_table(
        index=["date__year", "date__month"], 
        columns="transaction_type", 
        values="total", 
        fill_value=0
    ).reset_index()
 
    # 4. Ensure both columns exist (preventing KeyErrors if a user only has one type)
    if "income" not in pivot_df.columns:
        pivot_df["income"] = 0.0
    if "expense" not in pivot_df.columns:
        pivot_df["expense"] = 0.0

    # 5. Create the Prophet 'ds' (Date Stamp) column
    # We set it to the 1st of every month
    pivot_df["ds"] = pd.to_datetime(
        pivot_df["date__year"].astype(str) + "-" +
        pivot_df["date__month"].astype(str) + "-01"
    )

    # 6. Return cleaned DataFrame for Prophet
    return pivot_df[["ds", "income", "expense"]].sort_values("ds")