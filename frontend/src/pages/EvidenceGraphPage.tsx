import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import api from "../lib/api";
type Node = {id: string; kind: string; label: string; status?: string};
type Edge = {source: string; target: string; relation: string};
export default function EvidenceGraphPage() {
  const {data, isLoading, error} = useQuery<{nodes: Node[]; edges: Edge[]; warning: string}>({
    queryKey: ["evidence-graph"], queryFn: () => api.get("/intelligence/graph").then(r => r.data)});
  if (isLoading) return <p>Loading evidence graph…</p>;
  if (error || !data) return <p role="alert">Graph unavailable. Assessor access is required.</p>;
  const ids = new Set(data.edges.flatMap(e => [e.source,e.target]));
  const nodes = data.nodes.filter(n => ids.has(n.id));
  const positions = new Map(nodes.map((node,i) => [node.id, {x: 90 + (i % 5)*170, y: 55 + Math.floor(i/5)*100}]));
  return <div className="space-y-5">
    <h1 className="text-2xl font-bold">Claims evidence graph</h1>
    <p className="text-slate-600">{data.warning}</p>
    <p className="text-sm">Latest 200 claims. Blue: claim · Grey: claimant · Green: vehicle. Select a claim to inspect its dossier.</p>
    {!nodes.length ? <p>No linked claim records yet. Submit claims to populate the graph.</p> :
      <div className="overflow-auto border rounded-xl bg-white">
        <svg role="img" aria-label="Claim relationships" viewBox={"0 0 900 " + Math.max(250,Math.ceil(nodes.length/5)*100)} className="min-w-[800px]">
          {data.edges.map((edge,i) => {const a=positions.get(edge.source), b=positions.get(edge.target);
            return a && b ? <g key={i}><title>{edge.relation}</title>
              <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={edge.relation.includes("same_") ? "#cbd5e1" : "#e68a18"} strokeWidth="2"/></g> : null;})}
          {nodes.map(node => {const p=positions.get(node.id)!;
            const content=<g><title>{node.kind + ": " + node.id}</title>
              <circle cx={p.x} cy={p.y} r="22" fill={node.kind==="claim" ? "#2563eb" : node.kind==="vehicle" ? "#059669" : "#64748b"}/>
              <text x={p.x} y={p.y+38} textAnchor="middle" fontSize="11">{node.label}</text></g>;
            return node.kind==="claim" ? <Link key={node.id} to={"/claims/"+node.id} aria-label={"Open claim "+node.label}>{content}</Link> : <g key={node.id}>{content}</g>;})}
        </svg>
      </div>}
    <div className="bg-white border rounded-xl p-5">
      <h2 className="font-semibold mb-3">Relationship evidence</h2>
      {data.edges.map((edge,i) => <p key={i} className="text-sm py-1">
        <Link className="text-primary-600" to={"/claims/"+edge.source}>{edge.source.slice(0,8)}</Link>
        {" → " + edge.relation.replace(/_/g," ") + " → " + edge.target.slice(0,45)}
      </p>)}
    </div>
  </div>;
}
