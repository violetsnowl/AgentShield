import { useEffect, useState } from 'react';
import { api } from './api';
import { contractLine, enhancedPremium, parseAnnualSummary, percent, premiumRange, tierPremium, yuan } from './annualModel';
import type { AnnualSummary } from './annualModel';

/** 第三页：校准后的年度方案。Core、Plus 留在页面上作对照。 */
export function AnnualModelPanel() {
  const [summary, setSummary] = useState<AnnualSummary | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    api<unknown>('api/annual-model', { signal: controller.signal })
      .then(payload => setSummary(parseAnnualSummary(payload)))
      .catch(failure => { if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : '年度测算读取失败。'); });
    return () => controller.abort();
  }, []);
  if (error !== '') return <section className="real-batch" aria-label="年度方案"><p className="notice error" role="alert">{error}</p></section>;
  if (summary === null) return <div className="loading" role="status"><span className="spinner"/>正在读取年度测算…</div>;
  return <section className="real-batch" aria-label="年度方案" data-testid="annual-model">
    <div className="scenario-heading"><div><p className="eyebrow">校准后的方案</p>{summary.contracts.map(contract => <h2 key={contract.contract_version}>{contractLine(contract)}</h2>)}</div></div>
    <p className="fine-print">{summary.nature}。保费写成区间：下限不计资本成本，上限是计入资本成本的参考价，都不含再保；支出按下限计算。不是商业报价。两个按次免赔方案只作对照。</p>
    <div className="table-scroll"><table className="rec-table"><thead><tr><th>合同结构</th><th className="number">保费</th><th className="number">平均年度支出</th><th className="number">99% 分位</th><th className="number">最坏 1% 年份平均</th></tr></thead>
      <tbody>{summary.structures.map(row => <tr key={row.label}><td>{row.label}</td><td className="number">{premiumRange(row.premium_yuan, row.premium_capital_yuan)}</td><td className="number">{yuan(row.mean_yuan)}</td><td className="number">{yuan(row.p99_yuan)}</td><td className="number">{yuan(row.cte99_yuan)}</td></tr>)}</tbody></table></div>
    <div className="scenario-heading"><div><h2>配置决定保费</h2></div></div>
    <p className="fine-print">频率取事故率的 95% 区间上界，0 次事故也不按 0 定价。正式承保时用投保配置自己的测评结果。有赔款的年份接近 0 时，基础档基本不赔，可以不买。</p>
    <div className="table-scroll"><table className="rec-table"><thead><tr><th>配置</th><th>哨兵监测</th><th className="number">测评事故</th><th className="number">定价频率</th><th className="number">年预期事故</th><th className="number">不投保最坏 1%</th><th className="number">基础档保费</th><th className="number">基础档最坏 1%</th><th className="number">基础档有赔款的年份</th><th className="number">增强档保费</th><th className="number">增强档最坏 1%</th></tr></thead>
      <tbody>{summary.tiers.map(row => <tr key={`${row.tier}-${row.monitored}`}><td>{row.label}</td><td>{row.monitored ? '有' : '无'}</td><td className="number">{row.accidents}/{row.runs}</td><td className="number">{percent(row.pricing_frequency)}</td><td className="number">{row.expected_events}</td><td className="number">{yuan(row.uninsured_cte99_yuan)}</td><td className="number">{tierPremium(row)}</td><td className="number">{row.insurable ? yuan(row.insured_cte99_yuan) : '—'}</td><td className="number">{row.insurable ? percent(row.claim_year_chance) : '—'}</td><td className="number">{enhancedPremium(row)}</td><td className="number">{row.enhanced_offered ? yuan(row.enhanced_cte99_yuan) : '—'}</td></tr>)}</tbody></table></div>
    <div className="scenario-heading"><div><h2>发现得越早，批量事故越小</h2></div></div>
    <div className="table-scroll"><table className="rec-table"><thead><tr><th>从出错到止损</th>{summary.latency.map(row => <th className="number" key={row.hours}>{row.hours} 小时</th>)}</tr></thead>
      <tbody><tr><td>一次全错故障的损失</td>{summary.latency.map(row => <td className="number" key={row.hours}>{yuan(row.loud_fault_loss_yuan)}</td>)}</tr></tbody></table></div>
  </section>;
}
