from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..models import Expense, EmployeeLoan, User
from ..deps import current_user, require_roles
from ..schemas.common import ORMModel
from ..services.expense_service import create_expense, create_loan, repay_loan
from ..services.journal import JournalNotBalanced

router = APIRouter(prefix="/expenses", tags=["expenses"])
loan_router = APIRouter(prefix="/loans", tags=["loans"])


# ============================= BEBAN =============================
class ExpenseIn(BaseModel):
    date: date
    category: str = Field(default="umum", max_length=20)
    description: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(gt=0)
    expense_account_code: str = "6-2900"
    paid_account_code: str = "1-1000"
    note: str | None = None


class ExpenseOut(ORMModel):
    id: str
    number: str
    date: date
    category: str
    description: str
    amount: Decimal


@router.get("", response_model=list[ExpenseOut])
async def list_expenses(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    stmt = (select(Expense).where(Expense.company_id == user.company_id)
            .order_by(Expense.date.desc(), Expense.number.desc()).limit(200))
    return (await db.execute(stmt)).scalars().all()


@router.post("", response_model=ExpenseOut, status_code=201)
async def add_expense(
    body: ExpenseIn,
    user: User = Depends(require_roles("finance")),
    db: AsyncSession = Depends(get_db),
):
    try:
        exp = await create_expense(
            db, company_id=user.company_id, user_id=user.id,
            on_date=body.date, category=body.category,
            description=body.description, amount=body.amount,
            expense_account_code=body.expense_account_code,
            paid_account_code=body.paid_account_code, note=body.note,
        )
        await db.commit()
    except (JournalNotBalanced, ValueError) as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    await db.refresh(exp)
    return exp


# ============================= KASBON =============================
class LoanIn(BaseModel):
    employee_name: str = Field(min_length=1, max_length=120)
    date: date
    amount: Decimal = Field(gt=0)
    paid_account_code: str = "1-1000"
    note: str | None = None


class RepayIn(BaseModel):
    date: date
    amount: Decimal = Field(gt=0)
    cash_account_code: str = "1-1000"


class LoanOut(ORMModel):
    id: str
    number: str
    employee_name: str
    date: date
    amount: Decimal
    repaid_total: Decimal
    status: str


@loan_router.get("", response_model=list[LoanOut])
async def list_loans(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    stmt = (select(EmployeeLoan).where(EmployeeLoan.company_id == user.company_id)
            .order_by(EmployeeLoan.status, EmployeeLoan.date.desc()).limit(200))
    return (await db.execute(stmt)).scalars().all()


@loan_router.post("", response_model=LoanOut, status_code=201)
async def add_loan(
    body: LoanIn,
    user: User = Depends(require_roles("finance")),
    db: AsyncSession = Depends(get_db),
):
    try:
        loan = await create_loan(
            db, company_id=user.company_id, user_id=user.id,
            employee_name=body.employee_name, on_date=body.date,
            amount=body.amount, paid_account_code=body.paid_account_code,
            note=body.note,
        )
        await db.commit()
    except (JournalNotBalanced, ValueError) as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    await db.refresh(loan)
    return loan


@loan_router.post("/{loan_id}/repay", response_model=LoanOut)
async def repay(
    loan_id: str, body: RepayIn,
    user: User = Depends(require_roles("finance")),
    db: AsyncSession = Depends(get_db),
):
    try:
        loan = await repay_loan(
            db, company_id=user.company_id, user_id=user.id, loan_id=loan_id,
            on_date=body.date, amount=body.amount,
            cash_account_code=body.cash_account_code,
        )
        await db.commit()
    except (JournalNotBalanced, ValueError) as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        await db.rollback()
        raise
    await db.refresh(loan)
    return loan
