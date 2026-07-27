import { describe, expect, it } from 'vitest'

import type { CashFlowProjectionItem, RecurringTransaction } from '../types'
import {
  groupCashFlowMovements,
  projectionSourceKey,
  summarizeCashFlowPlan,
} from './cash-flow-plan'

const recurring = (type: 'debit' | 'credit', active = true) => ({
  type,
  is_active: active,
}) as RecurringTransaction

const item = (
  type: 'debit' | 'credit',
  amount: number,
  source: CashFlowProjectionItem['source'] = 'recurring',
) => ({
  type,
  amount_primary: amount,
  source,
  auto_generate: false,
}) as CashFlowProjectionItem

describe('cash-flow plan helpers', () => {
  it('summarizes active rules separately from projected occurrences', () => {
    expect(summarizeCashFlowPlan(
      [recurring('credit'), recurring('debit'), recurring('debit', false)],
      [item('credit', 1500), item('debit', 200), item('debit', 300)],
    )).toEqual({
      ruleCount: 2,
      incomeRuleCount: 1,
      expenseRuleCount: 1,
      projectedIncome: 1500,
      projectedExpenses: 500,
    })
  })

  it('uses distinct labels for planned, booked, and card-due movements', () => {
    expect(projectionSourceKey(item('debit', 10))).toBe('planned')
    expect(projectionSourceKey(item('debit', 10, 'booked'))).toBe('booked')
    expect(projectionSourceKey(item('debit', 10, 'credit_card'))).toBe('cardDue')
  })

  it('groups credit-card purchases by card and due date', () => {
    const first = {
      ...item('debit', 100, 'credit_card'),
      date: '2026-09-01',
      account_id: 'card-1',
      account_name: 'LATAM',
      description: 'Purchase A',
    } as CashFlowProjectionItem
    const second = {
      ...first,
      amount_primary: 250,
      description: 'Purchase B',
    }
    const salary = {
      ...item('credit', 1500),
      date: '2026-09-05',
      account_id: 'checking-1',
      account_name: 'Checking',
      description: 'Salary',
      recurring_id: 'salary-rule',
    } as CashFlowProjectionItem

    const movements = groupCashFlowMovements([first, second, salary])

    expect(movements).toHaveLength(2)
    expect(movements[0]).toMatchObject({
      sourceKey: 'cardDue',
      amountPrimary: 350,
      itemCount: 2,
    })
    expect(movements[1]).toMatchObject({ description: 'Salary', itemCount: 1 })
  })
})
