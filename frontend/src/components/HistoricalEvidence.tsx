import { useQueries } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import api from "../lib/api";
type Photograph = {id: string; original_url: string};
type Match = {claim_id: string; image_id: string; match_type: string; phash_distance?: number; dhash_distance?: number};
type Indicator = {code: string; image_id?: string; evidence?: {matches?: Match[]}};
export default function HistoricalEvidence({images,indicators}: {images: Photograph[]; indicators: Indicator[]}) {
  const pairs = indicators.filter(item => item.code === "duplicate_image")
    .flatMap(item => (item.evidence?.matches || []).map(match => ({imageId:item.image_id, match}))).slice(0,10);
  const claimIds = [...new Set(pairs.map(pair => pair.match.claim_id))];
  const queries = useQueries({queries: claimIds.map(id => ({
    queryKey:["claim",id], queryFn:()=>api.get("/claims/"+id).then(r=>r.data), retry:false}))});
  if (!pairs.length) return null;
  return <div className="space-y-4 mt-6">
    <h3 className="font-semibold">Matched historical photographs</h3>
    <p className="text-sm text-slate-500">Up to 10 matches. Perceptual candidates need visual confirmation. Reuse alone does not establish fraud.</p>
    {pairs.map(({imageId,match},i) => {
      const current=images.find(image=>image.id===imageId);
      const query=queries[claimIds.indexOf(match.claim_id)];
      const prior: Photograph | undefined=query?.data?.images?.find((image: Photograph)=>image.id===match.image_id);
      return <div key={i} className="border rounded-lg p-3 space-y-2">
        <Link className="text-primary-600 text-sm" to={"/claims/"+match.claim_id}>Historical claim {match.claim_id.slice(0,8)}</Link>
        <p className="text-xs">{match.match_type === "exact_file" ? "Exact file match" : "Perceptual candidate"}
          {" · pHash distance: " + match.phash_distance + " · dHash distance: " + match.dhash_distance}</p>
        <div className="grid grid-cols-2 gap-3">
          <figure>{current && <img src={current.original_url} alt="Current claim photograph" className="w-full h-48 object-contain bg-slate-100"/>}<figcaption className="text-xs">Current claim</figcaption></figure>
          <figure>{prior ? <img src={prior.original_url} alt="Matched historical photograph" className="w-full h-48 object-contain bg-slate-100"/> :
            <p className="text-sm text-slate-500">{query?.isPending ? "Loading historical image…" : "Historical photograph unavailable with this account."}</p>}
            <figcaption className="text-xs">Historical evidence</figcaption></figure>
        </div>
      </div>;
    })}
  </div>;
}
