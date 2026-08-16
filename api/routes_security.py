"""
ULTRON V3 - Security Confirmation REST API & Approval Routes
Securely exposes confirmation token validation to the UI frontend.
Direct OS execution is strictly prohibited; requests are validated against SessionManager.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from core.session import session


router = APIRouter(prefix="/api/security", tags=["security"])


class ConfirmationRequest(BaseModel):
    token_id: str
    approved: bool


@router.post("/confirm")
async def confirm_action(req: ConfirmationRequest):
    """
    Submit user confirmation response for a pending dangerous action.
    Validates token via SessionManager.
    """
    pending = session.pending_confirmation
    if not pending:
        raise HTTPException(status_code=400, detail="No pending security action found.")

    if session.is_confirmation_expired():
        session.clear_pending_confirmation()
        raise HTTPException(status_code=400, detail="Security token has expired.")

    if req.approved:
        token_id = req.token_id
        if pending.get("id") == token_id or pending.get("confirmation_id") == token_id:
            action = pending.get("action", "action")
            pending["validated"] = True
            pending["confirmed"] = True

            exec_func = pending.get("exec_func")
            res = None
            try:
                if exec_func:
                    res = exec_func()
            except Exception as e:
                res = f"Error: {e}"
            finally:
                session.clear_pending_confirmation()

            if res and isinstance(res, str) and ("Security block" in res or "Cannot" in res or "failed" in res or "Blocked" in res):
                raise HTTPException(status_code=400, detail=f"Action failed: {res}")

            return {"success": True, "message": f"Action '{action}' confirmed and authorized."}
        else:
            raise HTTPException(status_code=403, detail="Invalid or expired security token.")
    else:
        session.clear_pending_confirmation()
        return {"success": True, "message": "Action cancelled by user."}

