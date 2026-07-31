from pydantic import BaseModel
from uuid import UUID


class ReportBreakdown(BaseModel):
    key: str
    label: str
    value: float
    color: str


class ReportSummary(BaseModel):
    primary_value: float
    change_amount: float
    change_percent: float | None
    breakdowns: list[ReportBreakdown]


class ReportCompositionItem(BaseModel):
    key: str
    label: str
    value: float
    color: str
    group: str


class ReportDataPoint(BaseModel):
    date: str
    value: float
    breakdowns: dict[str, float]
    change: float | None = None
    composition: list[ReportCompositionItem] = []


class ReportMeta(BaseModel):
    type: str
    series_keys: list[str]
    currency: str
    interval: str
    forecast_start_date: str | None = None
    forecast_end_date: str | None = None
    baseline_active: bool = False
    baseline_lookback_days: int | None = None
    credit_card_accounting_mode: str | None = None
    confidence_layers: dict[str, float] = {}
    forecast_warnings: list["ForecastWarning"] = []


class CategoryTrendItem(BaseModel):
    key: str
    label: str
    color: str
    total: float
    group: str
    series: list[ReportDataPoint]


class CashFlowProjectionItem(BaseModel):
    date: str
    description: str
    amount: float
    amount_primary: float
    currency: str
    type: str
    source: str
    status: str
    account_id: UUID | None = None
    account_name: str
    account_type: str
    category_id: UUID | None = None
    category_name: str | None = None
    category_color: str | None = None
    recurring_id: UUID | None = None
    transaction_id: UUID | None = None
    auto_generate: bool | None = None
    origin: str = "unknown"
    effective_date: str = ""
    confidence: str = "estimated"
    confidence_score: float = 0.5
    installment_number: int | None = None
    total_installments: int | None = None
    installment_purchase_date: str | None = None


class ForecastWarning(BaseModel):
    code: str
    message: str
    account_id: UUID | None = None
    transaction_id: UUID | None = None
    missing_installments: list[int] = []


class ReportResponse(BaseModel):
    summary: ReportSummary
    trend: list[ReportDataPoint]
    meta: ReportMeta
    composition: list[ReportCompositionItem] = []
    category_trend: list[CategoryTrendItem] = []
    projection_items: list[CashFlowProjectionItem] = []
