from django.http import JsonResponse
import pandas as pd
from django.db.models import Sum
from forecast_app.models import Transaction

# import forecast service
from ai_engine.services.forecast_service import get_unified_forecast


# 1️⃣ CASH FLOW FORECAST
def cashflow_forecast_view(request):

    user = request.user
    month = int(request.GET.get("month", 2))
    year = int(request.GET.get("year", 2026))

    forecast = get_unified_forecast(user, month, year)

    if not forecast:
        return JsonResponse({"status": "insufficient_data"})

    risk_ratio = forecast["risk_ratio"]

    if risk_ratio >= 85:
        risk_level = "High"
        risk_color = "#e11d48"
    elif risk_ratio >= 60:
        risk_level = "Moderate"
        risk_color = "#d97706"
    else:
        risk_level = "Low"
        risk_color = "#059669"

    return JsonResponse({
        "status": "success",
        "expected_income": round(forecast["income"], 2),
        "expected_expense": round(forecast["expense"], 2),
        "expected_net_cash": round(forecast["net"], 2),
        "risk_percent": round(min(risk_ratio, 100.0), 1),
        "raw_risk_ratio": round(risk_ratio, 2),
        "risk_level": risk_level,
        "risk_color": risk_color
    })


# 2️⃣ CATEGORY TREND
def category_trend_view(request):

    user = request.user
    month = int(request.GET.get("month", 2))
    year = int(request.GET.get("year", 2026))

    forecast = get_unified_forecast(user, month, year)
    is_high_risk = forecast["is_high_risk"] if forecast else False

    qs = Transaction.objects.filter(
        user=user,
        transaction_type="expense"
    ).exclude(
        category__name__iexact="Savings"
    ).values("category__name", "date", "amount")

    df_raw = pd.DataFrame(list(qs))

    if df_raw.empty:
        return JsonResponse({"status": "no_data"})

    category_trends = []
    chart_labels = []
    chart_values = []

    unique_cats = df_raw["category__name"].unique()

    for cat in unique_cats:

        cat_df = df_raw[df_raw["category__name"] == cat].copy()

        cat_df = cat_df.rename(columns={
            "date": "ds",
            "amount": "y"
        })

        cat_df["ds"] = pd.to_datetime(cat_df["ds"])

        m_df = cat_df.set_index("ds").resample("MS")["y"].sum().reset_index()

        if len(m_df) >= 3:

            last = float(m_df.iloc[-1]["y"])
            prev = float(m_df.iloc[-2]["y"])

            momentum = last - prev

            chart_labels.append(cat)
            chart_values.append(round(last, 2))

            category_trends.append({
                "category": cat,
                "momentum": round(momentum, 2),
                "is_rising": momentum > 0,
                "predicted_total": round(last, 2)
            })

    sorted_data = sorted(
        zip(chart_labels, chart_values),
        key=lambda x: x[1],
        reverse=True
    )

    final_l, final_v = zip(*sorted_data) if sorted_data else ([], [])

    return JsonResponse({
        "status": "success",
        "category_trends": sorted(
            category_trends,
            key=lambda x: x["momentum"],
            reverse=True
        )[:6],
        "labels": list(final_l),
        "values": list(final_v),
        "is_high_risk": is_high_risk
    })


# 3️⃣ OVERSPENDING RISK
def overspending_risk_view(request):

    user = request.user
    month = int(request.GET.get("month", 1))
    year = int(request.GET.get("year", 2026))

    forecast = get_unified_forecast(user, month, year)

    if not forecast:
        return JsonResponse({"status": "no_data"})

    return JsonResponse({
        "status": "success",
        "overall_risk": "High" if forecast["is_high_risk"] else "Low",
        "is_negative": forecast["net"] < 0
    })


# 4️⃣ ANOMALIES
def expense_anomaly_view(request):

    user = request.user
    month = int(request.GET.get("month", 1))
    year = int(request.GET.get("year", 2026))

    forecast = get_unified_forecast(user, month, year)
    is_predicted_risk = forecast["is_high_risk"] if forecast else False

    expense_list = Transaction.objects.filter(
        user=user,
        transaction_type="expense"
    ).values("category__name").annotate(
        total=Sum("amount")
    ).order_by("-total")

    anomalies = []

    if is_predicted_risk and expense_list.exists():

        top_cat = expense_list[0]["category__name"]

        suggestion = (
            f"🚨 Immediate Budget Leak: High spending in "
            f"'{top_cat}' may drive a predicted ₹{abs(forecast['net']):,.0f} deficit."
        )

        for item in expense_list[:3]:
            anomalies.append({
                "category": item["category__name"],
                "type": "Risk Contributor"
            })

    else:
        suggestion = "Your finances look healthy. No anomalies predicted."

    return JsonResponse({
        "status": "success",
        "anomalies": anomalies,
        "suggestion": suggestion
    })


# 5️⃣ FINANCIAL PERSONALITY
def financial_personality_view(request):

    user = request.user
    month = int(request.GET.get("month", 1))
    year = int(request.GET.get("year", 2026))

    forecast = get_unified_forecast(user, month, year)

    if not forecast:
        return JsonResponse({"status": "no_data"})

    personality = (
        "At Risk"
        if forecast["is_high_risk"]
        else "Wealth Builder"
        if forecast["risk_ratio"] < 50
        else "Stable Planner"
    )

    return JsonResponse({
        "status": "success",
        "personality": personality
    })


# 6️⃣ FINANCIAL STRESS
def financial_stress_timeline_view(request):

    user = request.user
    month = int(request.GET.get("month", 1))
    year = int(request.GET.get("year", 2026))

    forecast = get_unified_forecast(user, month, year)

    return JsonResponse({
        "status": "success",
        "stress": "Critical"
        if (forecast and forecast["is_high_risk"])
        else "Safe"
    })



def build_month_index(df):

    df = df.copy()
    df["ym"] = df["date__year"] * 100 + df["date__month"]

    return df.sort_values("ym")


def budget_drift_view(request):

    user = request.user
    month = int(request.GET.get("month", 1))
    year = int(request.GET.get("year", 2026))

    target_ym = year * 100 + month

    qs = Transaction.objects.filter(user=user).values(
        "date__year",
        "date__month",
        "transaction_type"
    ).annotate(total=Sum("amount"))

    df = pd.DataFrame(list(qs))

    if df.empty:
        return JsonResponse({"status": "no_data"})

    df = build_month_index(df)
    df = df[df["ym"] <= target_ym]

    expenses = df[df["transaction_type"] == "expense"].groupby("ym")["total"].sum().astype(float)

    income = df[df["transaction_type"] == "income"].groupby("ym")["total"].sum().astype(float)

    if len(expenses) < 3:
        return JsonResponse({"status": "success", "drift_level": "Stable"})

    drift = (
        expenses.pct_change().fillna(0).mean()
        - income.reindex(expenses.index).pct_change().fillna(0).mean()
    )

    return JsonResponse({
        "status": "success",
        "drift_level": "Risky Drift" if drift > 0.1 else "Stable"
    })


def next_month_pressure_view(request):

    user = request.user
    month = int(request.GET.get("month", 1))
    year = int(request.GET.get("year", 2026))

    qs = Transaction.objects.filter(
        user=user,
        transaction_type="expense"
    ).values(
        "category__name",
        "date__year",
        "date__month"
    ).annotate(total=Sum("amount"))

    df = pd.DataFrame(list(qs))

    if df.empty:
        return JsonResponse({"status": "no_data"})

    df = build_month_index(df)

    target_ym = year * 100 + month

    df = df[df["ym"] < target_ym]

    pressure = []

    for cat in df["category__name"].unique():

        cdf = df[df["category__name"] == cat]

        if len(cdf) >= 2:

            momentum = float(cdf.iloc[-1]["total"]) - float(cdf.iloc[-2]["total"])

            if momentum > 0:

                pressure.append({
                    "category": cat,
                    "momentum": round(momentum, 2)
                })

    return JsonResponse({
        "status": "success",
        "pressure_categories": sorted(
            pressure,
            key=lambda x: x["momentum"],
            reverse=True
        )[:5]
    })