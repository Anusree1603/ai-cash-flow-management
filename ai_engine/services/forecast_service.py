import pandas as pd
from prophet import Prophet
from django.core.cache import cache
from ai_engine.utils import get_monthly_cashflow_df


def run_prophet_model(df, column):

    cache_key = f"prophet_model_{column}"

    model = cache.get(cache_key)

    if not model:

        m_df = df[['ds', column]].rename(columns={column: 'y'})

        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=False,
            daily_seasonality=False,
            changepoint_prior_scale=0.05
        )

        model.fit(m_df)

        cache.set(cache_key, model, timeout=3600)

    future = model.make_future_dataframe(periods=24, freq="MS")

    forecast = model.predict(future)

    return forecast


def get_unified_forecast(user, month, year):

    cache_key = f"forecast_{user.id}_{month}_{year}"
    cached = cache.get(cache_key)

    if cached:
        return cached

    df = get_monthly_cashflow_df(user)

    if df.empty or len(df) < 4:
        return None

    income_fc = run_prophet_model(df, "income")
    expense_fc = run_prophet_model(df, "expense")

    target_income = income_fc[
        (income_fc["ds"].dt.month == month) &
        (income_fc["ds"].dt.year == year)
    ]

    target_expense = expense_fc[
        (expense_fc["ds"].dt.month == month) &
        (expense_fc["ds"].dt.year == year)
    ]

    income = float(target_income["yhat"].iloc[0]) if not target_income.empty else 0
    expense = float(target_expense["yhat"].iloc[0]) if not target_expense.empty else 0

    net = income - expense

    risk_ratio = (expense / income * 100) if income > 0 else 100

    result = {
        "income": income,
        "expense": expense,
        "net": net,
        "risk_ratio": risk_ratio,
        "is_high_risk": net < 0 or risk_ratio > 85
    }

    cache.set(cache_key, result, timeout=3600)

    return result