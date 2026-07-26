import type { AgentToolCall } from "../lib/api";

interface ResultCardsProps {
  toolCalls: AgentToolCall[];
}

function RentFairnessCard({ result }: { result: Record<string, unknown> | null }) {
  if (!result) return null;
  const verdict = (result.verdict as string | undefined) ?? "unknown";
  const message = (result.message as string | undefined) ?? "Rent comparison is ready.";
  const difference = result.difference_from_average_pct;

  return (
    <div className="rounded-[24px] border border-white/15 bg-white/10 p-4 backdrop-blur-xl">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm uppercase tracking-[0.25em] text-zinc-400">Rent fairness</p>
        <span className="rounded-full border border-white/15 bg-black/25 px-2.5 py-1 text-[11px] uppercase tracking-[0.2em] text-zinc-200">
          {verdict}
        </span>
      </div>
      <p className="mt-3 text-lg text-white">{message}</p>
      {typeof difference === "number" ? <p className="mt-2 text-sm text-zinc-300">Difference from area average: {difference}%</p> : null}
    </div>
  );
}

function UtilityBadge({ result }: { result: Record<string, unknown> | null }) {
  if (!result) return null;
  const water = result.water_reliability_pct ?? "n/a";
  const electricityIssues = result.electricity_issue_count ?? 0;

  return (
    <div className="rounded-[24px] border border-white/15 bg-white/10 p-4 backdrop-blur-xl">
      <p className="text-sm uppercase tracking-[0.25em] text-zinc-400">Utility outlook</p>
      <p className="mt-3 text-lg text-white">Water reliability: {String(water)}%</p>
      <p className="mt-1 text-sm text-zinc-300">Electricity reports: {String(electricityIssues)}</p>
    </div>
  );
}

function ScamRiskAlert({ result }: { result: Record<string, unknown> | null }) {
  if (!result) return null;
  const risk = (result.risk_level as string | undefined) ?? "unknown";
  const reasons = Array.isArray(result.reasons) ? (result.reasons as string[]) : [];

  return (
    <div className="rounded-[24px] border border-white/15 bg-white/10 p-4 backdrop-blur-xl">
      <p className="text-sm uppercase tracking-[0.25em] text-zinc-400">Scam signal</p>
      <p className="mt-3 text-lg text-white">Risk level: {risk}</p>
      {reasons.length ? <ul className="mt-2 space-y-1 text-sm text-zinc-300">{reasons.map((item) => <li key={item}>• {item}</li>)}</ul> : null}
    </div>
  );
}

export function ResultCards({ toolCalls }: ResultCardsProps) {
  if (!toolCalls?.length) return null;
  const rent = toolCalls.find((tool) => tool.name === "checkRentFairness")?.result ?? null;
  const utility = toolCalls.find((tool) => tool.name === "checkUtilityReliability")?.result ?? null;
  const scam = toolCalls.find((tool) => tool.name === "flagScamRisk")?.result ?? null;

  return (
    <div className="mt-4 grid gap-3 md:grid-cols-3">
      <RentFairnessCard result={rent} />
      <UtilityBadge result={utility} />
      <ScamRiskAlert result={scam} />
    </div>
  );
}
