"use client";

import { FormEvent, useState } from "react";
import { alertSecurity, createReport, notifyAuthority, type UtilityReport } from "../lib/api";

interface HostelActionsProps {
  hostelId: string;
  initialReports: UtilityReport[];
}

interface FeedbackState {
  type: "success" | "error";
  message: string;
}

const inputClasses = "w-full rounded-2xl border border-white/15 bg-white/10 px-3 py-2.5 text-sm text-white outline-none transition focus:border-white/30 focus:bg-white/15 placeholder:text-zinc-500";

export function HostelActions({ hostelId, initialReports }: HostelActionsProps) {
  const [reports, setReports] = useState(initialReports);
  const [feedback, setFeedback] = useState<FeedbackState | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<"report" | "authority" | "security" | null>(null);
  const [reportForm, setReportForm] = useState({
    water_available: true,
    electricity_issue: false,
    comment: "",
  });
  const [authorityForm, setAuthorityForm] = useState({ issueType: "water", details: "Water issue reported for this property." });
  const [securityForm, setSecurityForm] = useState({ reason: "Possible scam listing", evidence: "Suspicious payment language reported by a student." });

  async function submitReport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const comment = reportForm.comment.trim();

    if (!comment) {
      setFeedback({ type: "error", message: "Please add a short comment so the report can be submitted." });
      return;
    }

    setIsSubmitting("report");
    setFeedback(null);

    try {
      const payload = await createReport(hostelId, {
        water_available: reportForm.water_available,
        electricity_issue: reportForm.electricity_issue,
        comment,
      });
      const created = payload.data.report as UtilityReport;
      setReports((current) => [created, ...current]);
      setReportForm({ water_available: true, electricity_issue: false, comment: "" });
      setFeedback({ type: "success", message: "Your utility report was shared successfully." });
    } catch (error) {
      setFeedback({ type: "error", message: error instanceof Error ? error.message : "Your report could not be sent right now." });
    } finally {
      setIsSubmitting(null);
    }
  }

  async function submitAuthority(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const details = authorityForm.details.trim();
    const issueType = authorityForm.issueType.trim();

    if (!issueType || !details) {
      setFeedback({ type: "error", message: "Please fill both the issue type and the details before notifying the authority." });
      return;
    }

    setIsSubmitting("authority");
    setFeedback(null);

    try {
      await notifyAuthority(hostelId, issueType, details);
      setAuthorityForm({ issueType: "water", details: "Water issue reported for this property." });
      setFeedback({ type: "success", message: "The authority notification was sent." });
    } catch (error) {
      setFeedback({ type: "error", message: error instanceof Error ? error.message : "The notification could not be sent." });
    } finally {
      setIsSubmitting(null);
    }
  }

  async function submitSecurity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const reason = securityForm.reason.trim();
    const evidence = securityForm.evidence.trim();

    if (!reason) {
      setFeedback({ type: "error", message: "Please add a reason before alerting security." });
      return;
    }

    setIsSubmitting("security");
    setFeedback(null);

    try {
      await alertSecurity(hostelId, reason, evidence);
      setSecurityForm({ reason: "Possible scam listing", evidence: "Suspicious payment language reported by a student." });
      setFeedback({ type: "success", message: "The security alert was sent successfully." });
    } catch (error) {
      setFeedback({ type: "error", message: error instanceof Error ? error.message : "The security alert could not be sent." });
    } finally {
      setIsSubmitting(null);
    }
  }

  return (
    <div className="space-y-4">
      {feedback ? (
        <div className={`rounded-2xl border px-4 py-3 text-sm ${feedback.type === "success" ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-200" : "border-rose-400/30 bg-rose-500/10 text-rose-200"}`}>
          {feedback.message}
        </div>
      ) : null}

      <div className="rounded-[28px] border border-white/15 bg-black/25 p-4 shadow-[0_20px_80px_rgba(0,0,0,0.24)] backdrop-blur-xl">
        <h2 className="text-xl font-semibold text-white">Report an issue</h2>
        <form onSubmit={submitReport} className="mt-4 space-y-3">
          <label className="flex items-center gap-2 text-sm text-zinc-300">
            <input type="checkbox" checked={reportForm.water_available} onChange={(event) => setReportForm((current) => ({ ...current, water_available: event.target.checked }))} className="h-4 w-4 rounded border-white/20 bg-white/10" />
            Water is available
          </label>
          <label className="flex items-center gap-2 text-sm text-zinc-300">
            <input type="checkbox" checked={reportForm.electricity_issue} onChange={(event) => setReportForm((current) => ({ ...current, electricity_issue: event.target.checked }))} className="h-4 w-4 rounded border-white/20 bg-white/10" />
            Electricity issue reported
          </label>
          <textarea
            value={reportForm.comment}
            onChange={(event) => setReportForm((current) => ({ ...current, comment: event.target.value }))}
            rows={3}
            placeholder="Add detail about the current situation"
            className={inputClasses}
          />
          <button type="submit" disabled={isSubmitting === "report"} className="rounded-full border border-white/15 bg-white/15 px-4 py-2 text-sm uppercase tracking-[0.2em] text-white transition hover:bg-white/20 disabled:cursor-not-allowed disabled:opacity-70">
            {isSubmitting === "report" ? "Sending…" : "Submit report"}
          </button>
        </form>
      </div>

      <div className="rounded-[28px] border border-white/15 bg-black/25 p-4 shadow-[0_20px_80px_rgba(0,0,0,0.24)] backdrop-blur-xl">
        <h2 className="text-xl font-semibold text-white">Escalation actions</h2>
        <div className="mt-4 space-y-3">
          <form onSubmit={submitAuthority} className="space-y-2 rounded-[20px] border border-white/10 bg-white/10 p-3">
            <input
              name="issueType"
              value={authorityForm.issueType}
              onChange={(event) => setAuthorityForm((current) => ({ ...current, issueType: event.target.value }))}
              className={inputClasses}
              placeholder="Issue type"
            />
            <textarea
              name="details"
              rows={2}
              value={authorityForm.details}
              onChange={(event) => setAuthorityForm((current) => ({ ...current, details: event.target.value }))}
              className={inputClasses}
              placeholder="Details"
            />
            <button type="submit" disabled={isSubmitting === "authority"} className="rounded-full border border-white/15 bg-white/15 px-4 py-2 text-sm uppercase tracking-[0.2em] text-white transition hover:bg-white/20 disabled:cursor-not-allowed disabled:opacity-70">
              {isSubmitting === "authority" ? "Sending…" : "Notify authority"}
            </button>
          </form>
          <form onSubmit={submitSecurity} className="space-y-2 rounded-[20px] border border-white/10 bg-white/10 p-3">
            <input
              name="reason"
              value={securityForm.reason}
              onChange={(event) => setSecurityForm((current) => ({ ...current, reason: event.target.value }))}
              className={inputClasses}
              placeholder="Reason"
            />
            <textarea
              name="evidence"
              rows={2}
              value={securityForm.evidence}
              onChange={(event) => setSecurityForm((current) => ({ ...current, evidence: event.target.value }))}
              className={inputClasses}
              placeholder="Evidence"
            />
            <button type="submit" disabled={isSubmitting === "security"} className="rounded-full border border-white/15 bg-white/15 px-4 py-2 text-sm uppercase tracking-[0.2em] text-white transition hover:bg-white/20 disabled:cursor-not-allowed disabled:opacity-70">
              {isSubmitting === "security" ? "Sending…" : "Alert security"}
            </button>
          </form>
        </div>
      </div>

      <div className="rounded-[28px] border border-white/15 bg-black/25 p-4 shadow-[0_20px_80px_rgba(0,0,0,0.24)] backdrop-blur-xl">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-xl font-semibold text-white">Recent crowd reports</h2>
          <span className="rounded-full border border-white/10 bg-white/10 px-3 py-1 text-[11px] uppercase tracking-[0.2em] text-zinc-300">{reports.length} total</span>
        </div>
        <div className="mt-4 space-y-3">
          {reports.length ? reports.map((report) => (
            <div key={report.id} className="rounded-[20px] border border-white/10 bg-white/10 p-3 text-sm text-zinc-300">
              <p>{report.comment}</p>
              <p className="mt-2 text-xs uppercase tracking-[0.2em] text-zinc-400">Water: {report.water_available ? "yes" : "no"} • Electricity: {report.electricity_issue ? "issue" : "stable"}</p>
            </div>
          )) : <p className="text-sm text-zinc-400">No reports yet.</p>}
        </div>
      </div>
    </div>
  );
}
