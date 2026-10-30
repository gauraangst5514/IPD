import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../lib/api";

export default function AssessmentForm({ claimId }: { claimId: string }) {
  const queryClient = useQueryClient();
  const [decision, setDecision] = useState("escalated");
  const [amount, setAmount] = useState("");
  const [notes, setNotes] = useState("");
  const mutation = useMutation({
    mutationFn: () => api.post("/assessments", {
      claim_id: claimId, decision, notes,
      approved_amount: decision === "approved" && amount !== "" ? Number(amount) : null,
    }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["claim", claimId] }),
        queryClient.invalidateQueries({ queryKey: ["review-queue"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-stats"] }),
      ]);
    },
  });
  return (
    <form className="card p-6 space-y-4" onSubmit={(event) => { event.preventDefault(); mutation.mutate(); }}>
      <h2 className="text-lg font-semibold">Assessor decision</h2>
      <p className="text-sm text-slate-500">Record your assessment after inspecting the evidence. An image match alone does not establish fraud.</p>
      <label className="block text-sm font-medium">
        Decision
        <select className="input mt-1" value={decision} onChange={(event) => setDecision(event.target.value)}>
          <option value="escalated">Escalate for investigation</option>
          <option value="approved">Approve claim</option>
          <option value="rejected">Reject claim</option>
        </select>
      </label>
      {decision === "approved" && (
        <label className="block text-sm font-medium">
          Approved amount (INR, optional)
          <input className="input mt-1" type="number" min="0" step="0.01" value={amount}
            onChange={(event) => setAmount(event.target.value)} />
        </label>
      )}
      <label className="block text-sm font-medium">
        Assessment notes
        <textarea className="input mt-1" rows={3} value={notes} required
          onChange={(event) => setNotes(event.target.value)} />
      </label>
      {mutation.isError && <p role="alert" className="text-sm text-red-600">Could not save the assessment. Check your access and try again.</p>}
      {mutation.isSuccess && <p role="status" className="text-sm text-emerald-700">Assessment saved.</p>}
      <button className="btn-primary" disabled={mutation.isPending} type="submit">
        {mutation.isPending ? "Saving..." : "Save assessment"}
      </button>
    </form>
  );
}
