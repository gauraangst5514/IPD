import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../lib/api";

type Result = { available?: boolean; model_score?: number; score_meaning?: string; reason?: string; graph_baseline?: Result;
  contributions?: {feature: string; log_odds: number}[]; explanation?: string;
  lines?: {description: string; quantity: number; unit_price: number; line_total: number}[];
  calculated_subtotal?: number; declared_total?: number; warning?: string; indicators?: {detail: string}[] };
const initial = {incident_severity: "Minor Damage", incident_type: "Single Vehicle Collision",
  insured_hobbies: "reading", total_claim_amount: "", vehicle_claim: "", umbrella_limit: "", policy_annual_premium: ""};

export default function IntelligenceDossier({claimId}: {claimId: string}) {
  const client = useQueryClient();
  const {data} = useQuery({queryKey: ["intelligence", claimId],
    queryFn: () => api.get("/intelligence/claims/" + claimId).then(r => r.data)});
  const [fields, setFields] = useState<Record<string, string>>(initial);
  const [invoice, setInvoice] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (data?.structured_fields && Object.keys(data.structured_fields).length)
      setFields(Object.fromEntries(Object.entries(data.structured_fields).map(([k,v]) => [k, String(v)])));
  }, [data]);
  async function submit(kind: "tabular" | "invoice") {
    setBusy(true); setError("");
    const numeric = new Set(["total_claim_amount", "vehicle_claim", "umbrella_limit", "policy_annual_premium"]);
    const body = kind === "invoice" ? {text: invoice} :
      Object.fromEntries(Object.entries(fields).map(([k,v]) => [k, numeric.has(k) ? Number(v) : v]));
    try {
      await api.post("/intelligence/claims/" + claimId + "/" + kind, body);
      await client.invalidateQueries({queryKey: ["intelligence", claimId]});
    } catch { setError("Assessment failed. Check all fields and service availability."); }
    finally { setBusy(false); }
  }
  const tabular: Result = data?.tabular || {};
  const parsed: Result = data?.invoice || {};
  return <section className="bg-white border rounded-xl p-6 space-y-5">
    <h2 className="text-lg font-semibold">Investigator workbench</h2>
    <p className="text-sm text-slate-600">Public-data research model. Enter documented claim facts. Its output is separate from image evidence and requires human review.</p>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    <form onSubmit={e => {e.preventDefault(); void submit("tabular");}} className="space-y-3">
      <h3 className="font-medium">Structured claim assessment</h3>
      <div className="grid md:grid-cols-2 gap-3">
        {Object.entries(fields).map(([key,value]) => <label key={key} className="text-sm capitalize">
          {key.replace(/_/g, " ")}
          {key === "incident_severity" || key === "incident_type" ?
            <select className="block w-full border rounded p-2" value={value} onChange={e => setFields({...fields,[key]: e.target.value})}>
              {(key === "incident_severity" ? ["Minor Damage","Major Damage","Total Loss","Trivial Damage"] :
                ["Single Vehicle Collision","Multi-vehicle Collision","Vehicle Theft","Parked Car"]).map(v => <option key={v}>{v}</option>)}
            </select> :
            <input required className="block w-full border rounded p-2" value={value}
              type={key === "insured_hobbies" ? "text" : "number"} step="any"
              onChange={e => setFields({...fields,[key]: e.target.value})}/>}
        </label>)}
      </div>
      <p className="text-xs text-slate-500">Use the benchmark dataset's units. Do not substitute the app's INR repair estimate. Hobby is retained only for reproducing the teammate baseline and needs an ablation/fairness review.</p>
      <button disabled={busy} className="bg-primary-600 text-white rounded px-4 py-2 disabled:opacity-50">Run learned baseline</button>
    </form>
    {tabular.available === false && <p className="text-amber-700">{tabular.reason || "Unsupported or missing input; no result generated."}</p>}
    {tabular.available && <div className="bg-slate-50 rounded p-4 space-y-2">
      <p className="font-semibold">Research classifier output: {((tabular.model_score || 0)*100).toFixed(1)}%</p>
      <p className="text-sm">{tabular.score_meaning}</p>
      <p className="text-xs">{tabular.explanation}</p>
      {tabular.graph_baseline?.available && <p className="text-sm border-l-2 border-blue-400 pl-3">
        GraphSAGE research output: {((tabular.graph_baseline.model_score || 0)*100).toFixed(1)}%.
        Neighbours are similar tabular records, not evidence of a fraud ring. This output is uncalibrated.
      </p>}
      <table className="w-full text-sm"><thead><tr><th className="text-left">Feature</th><th className="text-right">Log-odds contribution</th></tr></thead>
      <tbody>{tabular.contributions?.slice(0,10).map(c => <tr key={c.feature}><td>{c.feature}</td><td className="text-right">{c.log_odds.toFixed(3)}</td></tr>)}</tbody></table>
    </div>}
    <form onSubmit={e => {e.preventDefault(); void submit("invoice");}} className="border-t pt-4 space-y-3">
      <h3 className="font-medium">Invoice arithmetic</h3>
      <label className="block text-sm">Paste text as description | quantity | unit price. Add “Invoice total: amount” to compare.</label>
      <textarea required aria-label="Invoice text" value={invoice} onChange={e => setInvoice(e.target.value)}
        placeholder={"Bumper repair | 2 | 1500\nPaint | 1 | 2000\nInvoice total: 5000"} className="w-full border rounded p-3 h-28"/>
      <button disabled={busy} className="border rounded px-4 py-2">Check invoice</button>
    </form>
    {parsed.available === false && <p className="text-amber-700">{parsed.reason}</p>}
    {parsed.available && <div className="text-sm space-y-2">
      <p>Parsed subtotal: {parsed.calculated_subtotal?.toFixed(2)} · Declared total: {parsed.declared_total ?? "Not found"}</p>
      {parsed.lines?.map((line,i) => <p key={i}>{line.description}: {line.quantity} × {line.unit_price} = {line.line_total}</p>)}
      {parsed.indicators?.map((item,i) => <p key={i} className="text-amber-700">{item.detail}</p>)}
      <p className="text-slate-500">{parsed.warning}</p>
    </div>}
  </section>;
}
