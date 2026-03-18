"""
Finance Database & Expense Tracker
Handles all CRUD operations for expenses + budget analysis
"""

import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict
import json

# ============================================================
# DATABASE SETUP
# ============================================================

class FinanceDB:
    def __init__(self, db_path="finance.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Dict-like access
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                date TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT UNIQUE NOT NULL,
                monthly_limit REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS income (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL,
                source TEXT,
                date TEXT NOT NULL
            );
        """)

        # Insert default budget categories if empty
        cursor = self.conn.execute("SELECT COUNT(*) FROM budgets")
        if cursor.fetchone()[0] == 0:
            defaults = [
                ("food", 5000), ("transport", 2000), ("entertainment", 1500),
                ("shopping", 3000), ("bills", 4000), ("health", 1000),
                ("education", 2000), ("other", 2000)
            ]
            self.conn.executemany(
                "INSERT INTO budgets (category, monthly_limit) VALUES (?, ?)",
                defaults
            )
            self.conn.commit()

    def close(self):
        self.conn.close()


# ============================================================
# EXPENSE TRACKER
# ============================================================

# Categories the LLM will classify expenses into
CATEGORIES = [
    "food", "transport", "entertainment", "shopping",
    "bills", "health", "education", "other"
]

class ExpenseTracker:
    def __init__(self, db: FinanceDB):
        self.db = db

    def add_expense(self, amount: float, category: str, description: str = "", date: str = None):
        """Add a new expense. Returns the expense record."""
        if category not in CATEGORIES:
            category = "other"
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        self.db.conn.execute(
            "INSERT INTO expenses (amount, category, description, date) VALUES (?, ?, ?, ?)",
            (amount, category, description, date)
        )
        self.db.conn.commit()

        return {
            "amount": amount,
            "category": category,
            "description": description,
            "date": date,
            "status": "recorded"
        }

    def get_today_expenses(self):
        """Get all expenses for today."""
        today = datetime.now().strftime("%Y-%m-%d")
        rows = self.db.conn.execute(
            "SELECT * FROM expenses WHERE date = ? ORDER BY created_at DESC", (today,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_expenses_by_period(self, days=30):
        """Get expenses for the last N days."""
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = self.db.conn.execute(
            "SELECT * FROM expenses WHERE date >= ? ORDER BY date DESC", (start_date,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_category_totals(self, days=30):
        """Get spending totals by category for the last N days."""
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = self.db.conn.execute("""
            SELECT category, SUM(amount) as total, COUNT(*) as count
            FROM expenses WHERE date >= ?
            GROUP BY category ORDER BY total DESC
        """, (start_date,)).fetchall()
        return {r["category"]: {"total": r["total"], "count": r["count"]} for r in rows}

    def get_daily_totals(self, days=7):
        """Get daily spending totals for the last N days."""
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = self.db.conn.execute("""
            SELECT date, SUM(amount) as total
            FROM expenses WHERE date >= ?
            GROUP BY date ORDER BY date
        """, (start_date,)).fetchall()
        return [{"date": r["date"], "total": r["total"]} for r in rows]

    def get_total_spent(self, days=30):
        """Get total amount spent in the last N days."""
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        row = self.db.conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM expenses WHERE date >= ?",
            (start_date,)
        ).fetchone()
        return row["total"]


# ============================================================
# BUDGET ANALYZER
# ============================================================

class BudgetAnalyzer:
    def __init__(self, db: FinanceDB, tracker: ExpenseTracker):
        self.db = db
        self.tracker = tracker

    def get_budget_status(self):
        """Compare spending vs budget for each category (this month)."""
        # Get current month's spending
        now = datetime.now()
        first_of_month = now.replace(day=1).strftime("%Y-%m-%d")
        days_in_month = 30
        days_passed = now.day

        spending = self.db.conn.execute("""
            SELECT category, SUM(amount) as spent
            FROM expenses WHERE date >= ?
            GROUP BY category
        """, (first_of_month,)).fetchall()
        spending_map = {r["category"]: r["spent"] for r in spending}

        budgets = self.db.conn.execute("SELECT * FROM budgets").fetchall()

        status = []
        for b in budgets:
            cat = b["category"]
            limit = b["monthly_limit"]
            spent = spending_map.get(cat, 0)
            pct = (spent / limit * 100) if limit > 0 else 0
            projected = (spent / days_passed * days_in_month) if days_passed > 0 else 0

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
        """Generate smart insights about spending patterns."""
        insights = []
        status = self.get_budget_status()
        totals = self.tracker.get_category_totals(days=30)
        daily = self.tracker.get_daily_totals(days=7)

        # Check for over-budget categories
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

        # Check for spending spikes
        if len(daily) >= 3:
            avg = sum(d["total"] for d in daily) / len(daily)
            latest = daily[-1]["total"] if daily else 0
            if latest > avg * 1.5:
                insights.append(
                    f"Today's spending ({latest:.0f}) is significantly above "
                    f"your daily average ({avg:.0f})."
                )

        # Top spending category
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
        """
        Creates a financial context string to feed into the LLM
        so it can give personalized advice.
        """
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


# === Quick test ===
if __name__ == "__main__":
    db = FinanceDB("test_finance.db")
    tracker = ExpenseTracker(db)
    analyzer = BudgetAnalyzer(db, tracker)

    # Add some test expenses
    print("Adding test expenses...")
    tracker.add_expense(250, "food", "lunch at canteen")
    tracker.add_expense(150, "food", "coffee and snacks")
    tracker.add_expense(500, "transport", "uber to college")
    tracker.add_expense(1200, "shopping", "new headphones")
    tracker.add_expense(200, "entertainment", "movie tickets")

    # Check status
    print("\n--- Budget Status ---")
    for s in analyzer.get_budget_status():
        if s["spent"] > 0:
            print(f"  {s['category']}: {s['spent']}/{s['budget']} ({s['percentage']}%) [{s['status']}]")

    # Get insights
    print("\n--- Insights ---")
    for insight in analyzer.get_spending_insights():
        print(f"  {insight}")

    # Get LLM context
    print("\n--- LLM Context ---")
    print(analyzer.generate_context_for_llm())

    db.close()
    import os
    os.remove("test_finance.db")