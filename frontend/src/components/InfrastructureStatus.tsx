import { useQuery } from "@tanstack/react-query";
import api from "../lib/api";

type Service = {status: string; backend?: string; count?: number; pending_projections?: number};
export default function InfrastructureStatus() {
  const {data,isPending,isError}=useQuery<{status:string;services:Record<string,Service>}>({
    queryKey:["infrastructure"],queryFn:()=>api.get("/infrastructure").then(r=>r.data),
    refetchInterval:30000,retry:1,
  });
  return <section className="card p-5 mb-6" aria-label="Database and service health">
    <h2 className="font-semibold">Databases and background services</h2>
    <p className="text-sm text-slate-500 mt-1">{isPending?"Checking live connections…":isError?
      "The health endpoint could not be reached.":"Status reflects actual probes. Local mode uses SQL graph queries, local files and inline processing."}</p>
    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3 mt-4">
      {Object.entries(data?.services||{}).map(([name,service])=><div key={name} className="border rounded-lg p-3">
        <p className="font-medium capitalize text-sm">{name}{service.backend?" · "+service.backend:""}</p>
        <p className={service.status==="healthy"?"text-xs text-emerald-700":"text-xs text-slate-500"}>{service.status.replace(/_/g," ")}</p>
        {service.pending_projections!=null&&<p className="text-xs">Pending graph updates: {service.pending_projections}</p>}
        {service.count!=null&&<p className="text-xs">Workers: {service.count}</p>}
      </div>)}
    </div>
  </section>;
}
