"""HiTL (Human-in-the-Loop) FastAPI dashboard — the submission's Application URL."""
import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import select

from core.database import AsyncSessionFactory, init_db
from core.models import PendingAction, AnalysisReport
from core.seed import seed_products

app = FastAPI(title="MarketSense AI — HiTL Dashboard", version="0.1.0")


@app.on_event("startup")
async def startup():
    # Idempotent: creates the schema and seeds demo products if missing.
    # Done in-process (not a separate seed step) so deployment can't hang between steps.
    await init_db()
    try:
        await seed_products(create_tables=False)
    except Exception as e:  # seeding must never block the server from coming up
        import logging
        logging.getLogger("uvicorn.error").warning(f"Seed skipped: {e}")


@app.get("/health")
async def health():
    """Liveness probe — no DB dependency, returns 200 as soon as the server is up."""
    return {"status": "ok"}


# ── API ───────────────────────────────────────────────────────────────────────

class ReviewRequest(BaseModel):
    decision: str  # "approved" | "rejected"
    reviewer_note: Optional[str] = None


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Simple HTML dashboard for the demo — shows all pending actions."""
    async with AsyncSessionFactory() as db:
        actions = (
            await db.execute(
                select(PendingAction).order_by(PendingAction.created_at.desc()).limit(20)
            )
        ).scalars().all()

    rows = ""
    for a in actions:
        status_colour = {"pending": "#f59e0b", "approved": "#10b981", "rejected": "#ef4444"}.get(a.status, "#6b7280")
        rows += f"""
        <tr>
            <td><code>{a.id[:8]}…</code></td>
            <td><strong>{a.sku}</strong></td>
            <td>{a.action_type}</td>
            <td>PKR {a.action_payload.get('proposed_price', 0):,.0f}</td>
            <td style="color:{status_colour};font-weight:bold">{a.status.upper()}</td>
            <td>{a.created_at.strftime('%Y-%m-%d %H:%M') if a.created_at else '—'}</td>
            <td>
                {"" if a.status != "pending" else
                 f'<a href="/actions/{a.id}">Review →</a>'}
            </td>
        </tr>"""

    return HTMLResponse(f"""<!DOCTYPE html>
<html>
<head>
  <title>MarketSense AI — HiTL Dashboard</title>
  <style>
    body {{ font-family: system-ui, sans-serif; padding: 2rem; background: #0f172a; color: #e2e8f0; }}
    h1 {{ color: #38bdf8; }} h2 {{ color: #94a3b8; font-size: 1rem; font-weight: normal; margin-top: -1rem; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 1.5rem; }}
    th {{ background: #1e293b; padding: .75rem 1rem; text-align: left; color: #94a3b8; font-size: .875rem; }}
    td {{ padding: .75rem 1rem; border-bottom: 1px solid #1e293b; font-size: .875rem; }}
    a {{ color: #38bdf8; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <h1>MarketSense AI</h1>
  <h2>Human-in-the-Loop Approval Dashboard</h2>
  <table>
    <thead>
      <tr><th>ID</th><th>SKU</th><th>Action</th><th>Price</th><th>Status</th><th>Created</th><th></th></tr>
    </thead>
    <tbody>{rows or '<tr><td colspan="7" style="text-align:center;color:#94a3b8">No actions yet — trigger a demo run to see results.</td></tr>'}</tbody>
  </table>
</body>
</html>""")


@app.get("/actions/{action_id}", response_class=HTMLResponse)
async def action_detail(action_id: str):
    """Detail page for a single pending action with Approve / Reject buttons."""
    async with AsyncSessionFactory() as db:
        action = await db.get(PendingAction, action_id)
        if not action:
            raise HTTPException(status_code=404, detail="Action not found")
        report = await db.get(AnalysisReport, action.report_id)

    status_colour = {"pending": "#f59e0b", "approved": "#10b981", "rejected": "#ef4444"}.get(action.status, "#6b7280")
    buttons = ""
    if action.status == "pending":
        buttons = f"""
        <form method="post" action="/actions/{action_id}/review?decision=approved" style="display:inline">
          <button type="submit" style="background:#10b981;color:#fff;border:none;padding:.5rem 1.5rem;border-radius:.375rem;cursor:pointer;font-size:1rem;">
            ✓ Approve
          </button>
        </form>
        &nbsp;
        <form method="post" action="/actions/{action_id}/review?decision=rejected" style="display:inline">
          <button type="submit" style="background:#ef4444;color:#fff;border:none;padding:.5rem 1.5rem;border-radius:.375rem;cursor:pointer;font-size:1rem;">
            ✗ Reject
          </button>
        </form>"""

    draft_html = (action.draft_content or "").replace("\n", "<br>").replace("## ", "<strong>").replace("\n", "</strong><br>")

    return HTMLResponse(f"""<!DOCTYPE html>
<html>
<head>
  <title>Review Action — MarketSense AI</title>
  <style>
    body {{ font-family: system-ui, sans-serif; padding: 2rem; max-width: 720px; margin: 0 auto;
           background: #0f172a; color: #e2e8f0; }}
    h1 {{ color: #38bdf8; }} .back {{ color: #94a3b8; font-size: .875rem; }}
    .card {{ background: #1e293b; border-radius: .5rem; padding: 1.5rem; margin: 1rem 0; }}
    .status {{ color: {status_colour}; font-weight: bold; }}
    pre {{ background: #0f172a; padding: 1rem; border-radius: .375rem; overflow-x: auto;
           font-size: .8rem; white-space: pre-wrap; }}
    a {{ color: #38bdf8; }}
  </style>
</head>
<body>
  <p class="back"><a href="/">← All Actions</a></p>
  <h1>Review Pricing Action</h1>
  <div class="card">
    <p><strong>Action ID:</strong> <code>{action.id}</code></p>
    <p><strong>SKU:</strong> {action.sku} &nbsp;|&nbsp; <strong>Type:</strong> {action.action_type}</p>
    <p><strong>Proposed Price:</strong> PKR {action.action_payload.get('proposed_price', 0):,.0f}</p>
    <p><strong>Expected Margin:</strong> {action.action_payload.get('expected_margin', 0):.1f}%</p>
    <p><strong>Status:</strong> <span class="status">{action.status.upper()}</span></p>
    <hr style="border-color:#334155">
    <pre>{action.draft_content or '—'}</pre>
    <div style="margin-top:1.5rem">{buttons}</div>
  </div>
</body>
</html>""")


@app.post("/actions/{action_id}/review")
async def review_action(action_id: str, decision: str, reviewer_note: Optional[str] = None):
    """POST endpoint for approve/reject (used by the detail page form)."""
    if decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="decision must be 'approved' or 'rejected'")

    async with AsyncSessionFactory() as db:
        action = await db.get(PendingAction, action_id)
        if not action:
            raise HTTPException(status_code=404, detail="Action not found")
        if action.status != "pending":
            raise HTTPException(status_code=409, detail=f"Action already {action.status}")

        action.status = decision
        action.reviewer_note = reviewer_note
        action.reviewed_at = datetime.datetime.utcnow()
        await db.commit()

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/actions/{action_id}", status_code=303)


@app.get("/actions", response_model=list[dict])
async def list_actions(status: Optional[str] = None):
    """JSON API endpoint — list actions, optionally filtered by status."""
    async with AsyncSessionFactory() as db:
        q = select(PendingAction).order_by(PendingAction.created_at.desc())
        if status:
            q = q.where(PendingAction.status == status)
        actions = (await db.execute(q)).scalars().all()

    return [
        {
            "id": a.id,
            "report_id": a.report_id,
            "sku": a.sku,
            "action_type": a.action_type,
            "action_payload": a.action_payload,
            "status": a.status,
            "reviewer_note": a.reviewer_note,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "reviewed_at": a.reviewed_at.isoformat() if a.reviewed_at else None,
        }
        for a in actions
    ]
