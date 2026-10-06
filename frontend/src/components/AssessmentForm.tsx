import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../lib/api";

export default function AssessmentForm({ claimId, version }: { claimId: string; version: number }) {
  const [decision, setDecision] = useState("approved");
  const [amount, setAmount] = useState("");
  const [notes, setNotes] = useState("");
  const client = useQueryClient();
  const save = useMutation({
    mutationFn: () => api.post("/assessments", {
      claim_id: claimId, expected_version: version, decision, notes,
      approved_amount: decision === "approved" ? Number(amount) : null,
    }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["claim", claimId] });
      client.invalidateQueries({ queryKey: ["review-queue"] });
      client.invalidateQueries({ queryKey: ["dashboard-stats"] });
    },
  });
  return (
    <form className="space-y-4 rounded-xl border bg-white p-6" onSubmit={(event) => { event.preventDefault(); save.mutate(); }}>
      <h2 className="text-lg font-semibold">Assessor decision</h2>
      <label className="block">Decision
        <select value={decision} onChange={(event) => setDecision(event.target.value)} className="input mt-1">
          <option value="approved">Approve</option><option value="rejected">Reject</option><option value="escalated">Escalate</option>
        </select>
      </label>
      {decision === "approved" && <label className="block">Approved amount (₹)
        <input className="input mt-1" type="number" min="0" step="0.01" required value={amount} onChange={(event) => setAmount(event.target.value)} />
      </label>}
      <label className="block">Notes
        <textarea className="input mt-1" maxLength={5000} value={notes} onChange={(event) => setNotes(event.target.value)} />
      </label>
      <button className="btn-primary" disabled={save.isPending}>{save.isPending ? "Saving…" : "Save decision"}</button>
      {save.isError && <p role="alert" className="text-red-700">Decision could not be saved. The claim may have changed or been assigned to another assessor. Refresh before retrying.</p>}
    </form>
  );
}
