from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import streamlit as st
from auth.auth import get_authenticated_client

CATEGORIES = [
    "food", "transport", "entertainment", "shopping",
    "bills", "health", "education", "other"
]

def get_db():
    return get_authenticated_client(st.session_state.access_token)

def get_uid():
    return st.session_state.user_id

def now_local():
    """Returns current datetime in user's browser timezone."""
    tz = st.session_state.get("user_timezone", "UTC")
    return datetime.now(ZoneInfo(tz))

def today_local():
    """Returns today's date string in user's browser timezone."""
    return now_local().strftime("%Y-%m-%d")


# ============================================================
# EXPENSE TRACKER
# ============================================================

class ExpenseTracker:

    def add_expense(self, amount: float, category: str,
                    description: str = "", date: str = None):
        if category not in CATEGORIES:
            category = "other"
        db = get_db()
        db.table("expenses").insert({
            "user_id": get_uid(),
            "amount": amount,
            "category": category.lower(),
            "description": description,
            "date": date or today_local()
        }).execute()
        return {
            "amount": amount,
            "category": category,
            "description": description,
            "date": date or today_local(),
            "status": "recorded"
        }

    def get_today_expenses(self):
        today = today_local()
        db = get_db()
        rows = (db.table("expenses")
                  .select("*")
                  .eq("user_id", get_uid())
                  .eq("date", today)
                  .order("created_at", desc=True)
                  .execute().data)
        return rows

    def get_expenses(self, start_date: str = None, end_date: str = None):
        """Get expenses filtered by date range."""
        db = get_db()
        q = db.table("expenses").select("*").eq("user_id", get_uid())
        if start_date:
            q = q.gte("date", start_date)
        if end_date:
            q = q.lte("date", end_date)
        return q.order("date", desc=True).execute().data

    def get_expenses_by_period(self, days=30):
        start_date = (now_local() - timedelta(days=days)).strftime("%Y-%m-%d")
        db = get_db()
        rows = (db.table("expenses")
                  .select("*")
                  .eq("user_id", get_uid())
                  .gte("date", start_date)
                  .order("date", desc=True)
                  .execute().data)
        return rows

    def get_category_totals(self, days=30):
        rows = self.get_expenses_by_period(days=days)
        totals = {}
        for r in rows:
            cat = r["category"]
            if cat not in totals:
                totals[cat] = {"total": 0, "count": 0}
            totals[cat]["total"] += r["amount"]
            totals[cat]["count"] += 1
        return totals

    def get_daily_totals(self, days=7):
        start_date = (now_local() - timedelta(days=days)).strftime("%Y-%m-%d")
        db = get_db()
        rows = (db.table("expenses")
                  .select("date, amount")
                  .eq("user_id", get_uid())
                  .gte("date", start_date)
                  .execute().data)
        daily = {}
        for r in rows:
            d = str(r["date"])
            daily[d] = daily.get(d, 0) + r["amount"]
        return [{"date": d, "total": t} for d, t in sorted(daily.items())]

    def get_total_spent(self, days=30):
        rows = self.get_expenses_by_period(days=days)
        return sum(r["amount"] for r in rows)

    def undo_last_expense(self) -> dict | None:
        """
        Delete the most recently inserted expense for the current user.
        Returns the deleted expense dict, or None if there was nothing to undo.
        """
        db = get_db()
        rows = (db.table("expenses")
                  .select("*")
                  .eq("user_id", get_uid())
                  .order("created_at", desc=True)
                  .limit(1)
                  .execute().data)
        if not rows:
            return None
        expense = rows[0]
        db.table("expenses").delete().eq("id", expense["id"]).execute()
        return expense


# ============================================================
# BUDGET ANALYZER
# ============================================================

class BudgetAnalyzer:

    def __init__(self):
        self.tracker = ExpenseTracker()

    def get_budgets(self):
        db = get_db()
        rows = (db.table("budgets")
                  .select("*")
                  .eq("user_id", get_uid())
                  .execute().data)
        return {r["category"]: r["monthly_limit"] for r in rows}

    def set_budget(self, category: str, limit: float):
        db = get_db()
        db.table("budgets").upsert({
            "user_id": get_uid(),
            "category": category.lower(),
            "monthly_limit": limit
        }, on_conflict="user_id,category").execute()

    def get_budget_status(self):
        now = now_local()
        days_passed = now.day
        start_of_month = now.replace(day=1).strftime("%Y-%m-%d")

        # Use get_expenses with start_of_month for accurate monthly data
        rows = self.tracker.get_expenses(start_date=start_of_month)
        spending_map = {}
        for r in rows:
            cat = r["category"]
            spending_map[cat] = spending_map.get(cat, 0) + r["amount"]

        budgets = self.get_budgets()
        status = []
        for cat, limit in budgets.items():
            spent = spending_map.get(cat, 0)
            pct = (spent / limit * 100) if limit > 0 else 0
            projected = (spent / days_passed * 30) if days_passed > 0 else 0
            status.append({
                "category": cat,
                "budget": limit,
                "spent": spent,
                "remaining": limit - spent,
                "percentage": round(pct, 1),
                "projected_monthly": round(projected, 0),
                "status": "over" if pct > 100 else "warning" if pct > 75 else "ok"
            })
        return status

    def get_spending_insights(self):
        insights = []
        status = self.get_budget_status()
        totals = self.tracker.get_category_totals(days=30)
        daily = self.tracker.get_daily_totals(days=7)

        for s in status:
            if s["status"] == "over":
                insights.append(
                    f"You've exceeded your {s['category']} budget! "
                    f"Spent {s['spent']:.0f} of {s['budget']:.0f} limit."
                )
            elif s["status"] == "warning":
                insights.append(
                    f"Heads up: {s['category']} is at {s['percentage']}% of budget."
                )

        if len(daily) >= 3:
            avg = sum(d["total"] for d in daily) / len(daily)
            latest = daily[-1]["total"] if daily else 0
            if latest > avg * 1.5:
                insights.append(
                    f"Today's spending ({latest:.0f}) is significantly above "
                    f"your daily average ({avg:.0f})."
                )

        if totals:
            top_cat = max(totals.items(), key=lambda x: x[1]["total"])
            insights.append(
                f"Your biggest expense category this month: {top_cat[0]} "
                f"at {top_cat[1]['total']:.0f}."
            )

        if not insights:
            insights.append("Looking good! Your spending is well within budget.")

        return insights

    def generate_context_for_llm(self):
        status = self.get_budget_status()
        insights = self.get_spending_insights()
        total_month = self.tracker.get_total_spent(days=30)
        total_today = sum(e["amount"] for e in self.tracker.get_today_expenses())

        context = f"""
USER'S FINANCIAL SNAPSHOT:
- Total spent this month: {total_month:.0f}
- Total spent today: {total_today:.0f}

BUDGET STATUS:
"""
        for s in status:
            if s["spent"] > 0:
                context += f"- {s['category']}: spent {s['spent']:.0f}/{s['budget']:.0f} ({s['percentage']}%)\n"

        context += "\nINSIGHTS:\n"
        for insight in insights:
            context += f"- {insight}\n"

        return context


# ============================================================
# INCOME TRACKER
# ============================================================

class IncomeTracker:

    def add_income(self, amount: float, source: str = "",
                   income_date: str = None):
        db = get_db()
        db.table("income").insert({
            "user_id": get_uid(),
            "amount": amount,
            "source": source,
            "date": income_date or today_local()
        }).execute()


# ============================================================
# CHAT HISTORY
# ============================================================

class ChatHistory:

    def save_message(self, role: str, content: str):
        db = get_db()
        db.table("chat_history").insert({
            "user_id": get_uid(),
            "role": role,
            "content": content
        }).execute()

    def load_history(self, limit: int = 20):
        db = get_db()
        rows = (db.table("chat_history")
                  .select("role, content")
                  .eq("user_id", get_uid())
                  .order("created_at", desc=False)
                  .limit(limit)
                  .execute().data)
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    def clear_history(self):
        db = get_db()
        db.table("chat_history").delete().eq("user_id", get_uid()).execute()