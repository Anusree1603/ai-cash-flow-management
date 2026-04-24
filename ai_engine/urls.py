from django.urls import path
from ai_engine import views   # import the whole views module

urlpatterns = [
    path("cashflow/", views.cashflow_forecast_view, name="cashflow_forecast"),
    path("category-trend/", views.category_trend_view, name="category_trend"),
    path("overspending-risk/", views.overspending_risk_view, name="overspending_risk"),
    path("expense-anomaly/", views.expense_anomaly_view),
    path("budget-drift/", views.budget_drift_view),
    path("next-month-pressure/", views.next_month_pressure_view),
    path("financial-personality/", views.financial_personality_view),
    path("stress-timeline/", views.financial_stress_timeline_view),
    
]
