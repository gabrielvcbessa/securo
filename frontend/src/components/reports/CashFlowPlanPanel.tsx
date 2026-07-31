import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, ArrowDownLeft, ArrowUpRight, CalendarClock, Settings2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { accounts as accountsApi, recurring as recurringApi } from '@/lib/api'
import { groupCashFlowMovements, summarizeCashFlowPlan } from '@/lib/cash-flow-plan'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import type { ReportResponse } from '@/types'

interface Props {
  report: ReportResponse
  baseline: boolean
  accountIds?: string[]
  locale: string
  formatAmount: (value: number) => string
  onUseMyPlan: () => void
}

export function CashFlowPlanPanel({
  report,
  baseline,
  accountIds,
  locale,
  formatAmount,
  onUseMyPlan,
}: Props) {
  const { t } = useTranslation()
  const [showAll, setShowAll] = useState(false)
  const accountQuery = useQuery({
    queryKey: ['accounts'],
    queryFn: () => accountsApi.list(),
  })
  const recurringQuery = useQuery({
    queryKey: ['recurring'],
    queryFn: recurringApi.list,
  })
  const accounts = accountQuery.data ?? []
  const recurring = recurringQuery.data ?? []

  const includedAccounts = accountIds
    ? accounts.filter((account) => accountIds.includes(account.id))
    : accounts
  const includedIds = new Set(includedAccounts.map((account) => account.id))
  const includedRecurring = recurring.filter((rule) => includedIds.has(rule.account_id ?? ''))
  const items = report.projection_items ?? []
  const summary = summarizeCashFlowPlan(includedRecurring, items)
  const movements = groupCashFlowMovements(items)
  const visibleMovements = showAll ? movements : movements.slice(0, 8)
  const lookbackDays = report.meta.baseline_lookback_days ?? 0
  const layers = report.meta.confidence_layers
  const warnings = report.meta.forecast_warnings ?? []

  if (baseline) {
    return (
      <section className="bg-card rounded-xl border border-border shadow-sm mb-5 px-5 py-5">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-foreground">{t('reports.recentActivityTitle')}</p>
            <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
              {t('reports.recentActivityDescription', { days: lookbackDays })}
            </p>
            {lookbackDays > 0 && lookbackDays < 60 && (
              <p className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-amber-700 dark:text-amber-400">
                <AlertTriangle size={14} />
                {t('reports.earlyEstimate')}
              </p>
            )}
          </div>
          <Button type="button" variant="outline" size="sm" onClick={onUseMyPlan}>
            {t('reports.useMyPlan')}
          </Button>
        </div>
      </section>
    )
  }

  if (accountQuery.isPending || recurringQuery.isPending) {
    return <Skeleton className="h-56 w-full rounded-xl mb-5" />
  }

  if (accountQuery.isError || recurringQuery.isError) {
    return (
      <section className="bg-card rounded-xl border border-border shadow-sm mb-5 px-5 py-5">
        <p className="text-sm text-rose-600">{t('reports.setupLoadError')}</p>
        <Button
          className="mt-3"
          type="button"
          variant="outline"
          size="sm"
          onClick={() => {
            accountQuery.refetch()
            recurringQuery.refetch()
          }}
        >
          {t('common.retry')}
        </Button>
      </section>
    )
  }

  return (
    <section className="bg-card rounded-xl border border-border shadow-sm mb-5 overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-foreground">{t('reports.forecastSetup')}</p>
          <p className="text-xs text-muted-foreground mt-1">{t('reports.myPlanSource')}</p>
        </div>
        <Button asChild variant="outline" size="sm">
          <Link to="/recurring"><Settings2 size={14} />{t('reports.managePlan')}</Link>
        </Button>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-px bg-border">
        <PlanMetric label={t('reports.includedAccounts')} value={String(includedAccounts.length)} />
        <PlanMetric label={t('reports.activeRules')} value={String(summary.ruleCount)} />
        <PlanMetric
          label={t('reports.plannedInflows')}
          value={formatAmount(summary.projectedIncome)}
          tone="positive"
        />
        <PlanMetric
          label={t('reports.plannedOutflows')}
          value={formatAmount(summary.projectedExpenses)}
          tone="negative"
        />
      </div>

      {layers && (
        <div className="grid grid-cols-3 gap-px bg-border border-t border-border">
          <PlanMetric label={t('reports.actualLayer')} value={formatAmount(layers.actual ?? 0)} />
          <PlanMetric label={t('reports.committedLayer')} value={formatAmount(layers.committed ?? 0)} />
          <PlanMetric label={t('reports.estimatedLayer')} value={formatAmount(layers.estimated ?? 0)} />
        </div>
      )}

      {warnings.length > 0 && (
        <div className="mx-5 mt-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-3 text-xs text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-300">
          <p className="font-semibold">
            <AlertTriangle size={14} className="inline mr-1.5 -mt-0.5" />
            {t('reports.forecastWarnings', { count: warnings.length })}
          </p>
          <ul className="mt-2 list-disc pl-5 space-y-1">
            {warnings.slice(0, 3).map((warning) => (
              <li key={`${warning.transaction_id}:${warning.code}`}>{warning.message}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="px-5 py-4 border-b border-border flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted-foreground">
        <span>
          {t('reports.cardTiming')}:{' '}
          <strong className="text-foreground">
            {report.meta.credit_card_accounting_mode === 'accrual'
              ? t('reports.billDueDate')
              : t('reports.purchaseDate')}
          </strong>
        </span>
        <span>{t('reports.ruleMix', {
          income: summary.incomeRuleCount,
          expenses: summary.expenseRuleCount,
        })}</span>
      </div>

      {includedAccounts.length === 0 ? (
        <div className="px-5 py-8 text-center border-b border-border">
          <CalendarClock className="mx-auto h-8 w-8 text-muted-foreground/60" />
          <p className="text-sm font-semibold text-foreground mt-3">
            {t(accountIds ? 'reports.noScopedAccountsTitle' : 'reports.noAccountsTitle')}
          </p>
          <p className="text-sm text-muted-foreground mt-1">
            {t(accountIds ? 'reports.noScopedAccountsDescription' : 'reports.noAccountsDescription')}
          </p>
          <Button asChild size="sm" className="mt-4">
            <Link to="/accounts">{t('reports.manageAccounts')}</Link>
          </Button>
        </div>
      ) : summary.ruleCount === 0 ? (
        <div className="px-5 py-8 text-center">
          <CalendarClock className="mx-auto h-8 w-8 text-muted-foreground/60" />
          <p className="text-sm font-semibold text-foreground mt-3">{t('reports.noPlanTitle')}</p>
          <p className="text-sm text-muted-foreground mt-1">{t('reports.noPlanDescription')}</p>
          <div className="mt-4 flex flex-wrap justify-center gap-2">
            <Button asChild size="sm"><Link to="/recurring?new=credit">{t('reports.addIncome')}</Link></Button>
            <Button asChild size="sm" variant="outline"><Link to="/recurring?new=debit">{t('reports.addExpense')}</Link></Button>
          </div>
        </div>
      ) : null}

      {includedAccounts.length > 0 && summary.ruleCount > 0 && summary.incomeRuleCount === 0 && (
            <div className="mx-5 mt-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-xs text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-300">
              <AlertTriangle size={14} className="inline mr-1.5 -mt-0.5" />
              {t('reports.noPlannedIncome')}
              {' '}
              <Link className="font-semibold underline underline-offset-2" to="/recurring?new=credit">
                {t('reports.addIncome')}
              </Link>
            </div>
      )}

      {includedAccounts.length > 0 && (
          <div className="px-5 py-4">
            <p className="text-sm font-semibold text-foreground">{t('reports.upcomingMovements')}</p>
            {visibleMovements.length === 0 ? (
              <p className="text-sm text-muted-foreground py-6 text-center">
                {t('reports.noMovementsInRange')}
              </p>
            ) : (
              <ul className="mt-2 divide-y divide-border">
                {visibleMovements.map((item) => (
                  <li key={item.key} className="py-3 flex items-center gap-3">
                    <span className={`rounded-full p-2 ${
                      item.type === 'credit'
                        ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40'
                        : 'bg-rose-50 text-rose-600 dark:bg-rose-950/40'
                    }`}>
                      {item.type === 'credit' ? <ArrowDownLeft size={15} /> : <ArrowUpRight size={15} />}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-foreground truncate">
                        {item.sourceKey === 'cardDue'
                          ? t('reports.cardBillLabel', { account: item.accountName })
                          : item.description}
                      </p>
                      <p className="text-xs text-muted-foreground truncate">
                        {new Date(`${item.date}T00:00:00`).toLocaleDateString(locale)}
                        {' · '}{item.accountName}
                        {' · '}{t(`reports.${item.sourceKey}`)}
                        {' · '}{t(`reports.confidence.${item.confidence}`)}
                        {item.installmentNumber && item.totalInstallments
                          ? ` · ${item.installmentNumber}/${item.totalInstallments}`
                          : ''}
                        {item.itemCount > 1 && ` · ${t('reports.cardPurchaseCount', { count: item.itemCount })}`}
                      </p>
                    </div>
                    <span className={`text-sm font-semibold tabular-nums ${
                      item.type === 'credit' ? 'text-emerald-600' : 'text-rose-600'
                    }`}>
                      {item.type === 'credit' ? '+' : '−'}
                      {formatAmount(item.amountPrimary)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            {movements.length > 8 && (
              <button
                type="button"
                className="mt-2 text-xs font-semibold text-primary hover:underline"
                onClick={() => setShowAll((value) => !value)}
                aria-expanded={showAll}
              >
                {showAll ? t('reports.showLess') : t('reports.showAllMovements', { count: movements.length })}
              </button>
            )}
          </div>
      )}
    </section>
  )
}

function PlanMetric({
  label,
  value,
  tone,
}: {
  label: string
  value: string
  tone?: 'positive' | 'negative'
}) {
  return (
    <div className="bg-card px-5 py-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={`text-lg font-bold tabular-nums mt-0.5 ${
        tone === 'positive' ? 'text-emerald-600' : tone === 'negative' ? 'text-rose-600' : 'text-foreground'
      }`}>{value}</p>
    </div>
  )
}
