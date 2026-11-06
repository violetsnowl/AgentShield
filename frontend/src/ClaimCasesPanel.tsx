import { useEffect, useState } from 'react';
import { api } from './api';
import { accidentRate, claimSummary, parseClaimCatalog, payoutLabel, rateRange, saveClaimExport } from './claimCases';
import type { ClaimCase, ClaimCatalog, ClaimExport } from './claimCases';
import { money } from './data';

const SHOWN_CASES = 8;

function ExportButton({ row }: { row: ClaimCase }) {
  const [state, setState] = useState<'idle' | 'busy' | 'done'>('idle');
  const [error, setError] = useState('');
  if (!row.available) return <span className="cell-note">原始证据不在本机</span>;
  const run = async () => {
    setState('busy');
    setError('');
    try {
      saveClaimExport(await api<ClaimExport>(`api/claim-cases/${row.case_id}/pack`));
      setState('done');
    } catch (failure) {
      setState('idle');
      setError(failure instanceof Error ? failure.message : '导出失败，请重试。');
    }
  };
  return <>
    <button type="button" className="text-button" data-testid="claim-export" disabled={state === 'busy'} onClick={() => void run()}>{state === 'busy' ? '导出中…' : state === 'done' ? '已导出' : '导出理赔材料'}</button>
    {error !== '' && <span className="cell-note" role="alert">{error}</span>}
  </>;
}

/** 真实 Agent 模式第二页：不依赖当前批次，直接展示已跑完的权限档位对照和真实事故。 */
export function ClaimCasesPanel() {
  const [catalog, setCatalog] = useState<ClaimCatalog | null>(null);
  const [error, setError] = useState('');
  const [expanded, setExpanded] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    api<unknown>('api/claim-cases', { signal: controller.signal })
      .then(payload => setCatalog(parseClaimCatalog(payload)))
      .catch(failure => { if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : '实验结果读取失败。'); });
    return () => controller.abort();
  }, []);
  if (error !== '') return <section className="real-batch" aria-label="权限档位对照"><p className="notice error" role="alert">{error}</p></section>;
  if (catalog === null) return <div className="loading" role="status"><span className="spinner"/>正在读取实验结果…</div>;
  if (catalog.arms.length === 0) return null;
  const summary = claimSummary(catalog);
  const cases = expanded ? catalog.cases : catalog.cases.slice(0, SHOWN_CASES);
  return <section className="real-batch" aria-label="权限档位对照" data-testid="claim-cases">
    <div className="scenario-heading"><div><p className="eyebrow">已完成的实验</p><h2>同一批任务，换权限档位的结果</h2></div></div>
    <p className="fine-print">{catalog.experiment_nature}。事故指净损失不低于 ¥1 的运行。各行运行数不同时，看事故率，不比较净损失合计。</p>
    <div className="table-scroll"><table className="rec-table"><thead><tr><th>模型</th><th>任务</th><th>权限档位</th><th className="number">运行</th><th className="number">事故</th><th className="number">事故率</th><th className="number">95% 区间</th><th className="number">净损失合计</th><th className="number">被网关拦下</th></tr></thead>
      <tbody>{catalog.arms.map(arm => <tr key={`${arm.batch_id}-${arm.control_profile}`}><td>{arm.model}</td><td>{arm.tasks}</td><td>{arm.control_label}</td><td className="number">{arm.runs}</td><td className="number">{arm.accidents}</td><td className="number">{accidentRate(arm)}</td><td className="number">{rateRange(arm)}</td><td className="number">{money(arm.net_loss_cents)}</td><td className="number">{arm.blocked_runs}</td></tr>)}</tbody></table></div>
    {catalog.cases.length > 0 && <>
      <div className="scenario-heading"><div><h2>真实事故与理赔材料</h2></div></div>
      <p className="fine-print">共 {summary.count} 起，净损失合计 {money(summary.lossCents)}，已理算的研究赔款合计 {money(summary.assessedPayoutCents)}{summary.pending > 0 ? `，另有 ${summary.pending} 起待人工认定` : ''}。赔款按研究合同试算，不是商业报价。导出时从原始证据重新计算，算不上的金额不会出现在材料里。</p>
      <div className="table-scroll"><table className="rec-table"><thead><tr><th>模型</th><th>权限档位</th><th>任务类型</th><th className="number">净损失</th><th className="number">研究赔款</th><th>材料</th></tr></thead>
        <tbody>{cases.map(row => <tr key={row.case_id}><td>{row.model}</td><td>{row.control_label}</td><td>{row.family_label}</td><td className="number">{money(row.net_loss_cents)}</td><td className="number">{payoutLabel(row)}</td><td><ExportButton row={row}/></td></tr>)}</tbody></table></div>
      {catalog.cases.length > SHOWN_CASES && <button type="button" className="text-button" onClick={() => setExpanded(value => !value)}>{expanded ? `只看净损失最大的 ${SHOWN_CASES} 起` : `查看全部 ${catalog.cases.length} 起`}</button>}
    </>}
  </section>;
}
