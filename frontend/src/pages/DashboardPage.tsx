import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "../store/auth";
import { Link } from "react-router-dom";
import { FileText, AlertTriangle, CheckCircle, Clock, XCircle, Shield, TrendingUp, ArrowRight } from "lucide-react";
import api from "../lib/api";
import ComponentStatus from "../components/ComponentStatus";
import InfrastructureStatus from "../components/InfrastructureStatus";

interface RecentClaim {
  id: string;
  status: string;
  damage_type: string | null;
  fraud_risk_score: number | null;
  created_at: string | null;
}

export default function DashboardPage() {
  const { fullName, role } = useAuthStore();

  const { data: stats } = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: () => api.get("/stats").then((r) => r.data),
  });

  const statCards = [
    { label: "Total Claims", value: stats?.total ?? "–", icon: FileText, color: "text-indigo-600", bg: "bg-indigo-50" },
    { label: "Pending Review", value: stats?.pending ?? "–", icon: Clock, color: "text-amber-600", bg: "bg-amber-50" },
    { label: "Approved", value: stats?.approved ?? "–", icon: CheckCircle, color: "text-emerald-600", bg: "bg-emerald-50" },
    { label: "Flagged", value: stats?.flagged ?? "–", icon: AlertTriangle, color: "text-rose-600", bg: "bg-rose-50" },
  ];

  return (
    <div className="max-w-6xl">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">
          Welcome back, {fullName}
        </h1>
        <p className="text-slate-500 text-sm mt-1">
          {role === "claimant" && "Manage your insurance claims and track their status."}
          {role === "assessor" && "Review and assess pending insurance claims."}
          {role === "admin" && "System overview and management dashboard."}
        </p>
      </div>

      {(role==="admin" || role==="assessor") && <InfrastructureStatus/>}
      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
        {statCards.map((stat) => {
          const Icon = stat.icon;
          return (
            <div key={stat.label} className="card p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-500">{stat.label}</p>
                  <p className="text-2xl font-bold text-slate-900 mt-1">{stat.value}</p>
                </div>
                <div className={`w-10 h-10 rounded-lg ${stat.bg} flex items-center justify-center`}>
                  <Icon className={`w-5 h-5 ${stat.color}`} />
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <ComponentStatus />

      {/* Assessor/Admin extra stats */}
      {(role === "assessor" || role === "admin") && stats !== undefined && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-8">
          <div className="card p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-500">Claims with review indicators</p>
                <p className="text-2xl font-bold text-slate-900 mt-1">
                  {stats.flagged ?? 0}
                </p>
              </div>
              <div className="w-10 h-10 rounded-lg bg-orange-50 flex items-center justify-center">
                <Shield className="w-5 h-5 text-orange-600" />
              </div>
            </div>
          </div>
          <div className="card p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-500">Rejected</p>
                <p className="text-2xl font-bold text-slate-900 mt-1">{stats.rejected ?? 0}</p>
              </div>
              <div className="w-10 h-10 rounded-lg bg-red-50 flex items-center justify-center">
                <XCircle className="w-5 h-5 text-red-600" />
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Recent Claims */}
        <div className="lg:col-span-2 card p-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-base font-semibold text-slate-900">Recent Claims</h2>
            <Link to="/claims" className="text-sm text-primary-600 hover:text-primary-700 font-medium flex items-center gap-1">
              View all <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          {stats?.recent_claims?.length > 0 ? (
            <div className="space-y-2.5">
              {stats.recent_claims.map((claim: RecentClaim) => (
                <Link
                  key={claim.id}
                  to={`/claims/${claim.id}`}
                  className="flex items-center justify-between p-3.5 rounded-lg border border-slate-100 hover:border-primary-200 hover:bg-primary-50/30 transition-all duration-150"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`badge ${
                        claim.status === "approved"
                          ? "bg-emerald-50 text-emerald-700"
                          : claim.status === "rejected"
                          ? "bg-red-50 text-red-700"
                          : claim.status === "flagged"
                          ? "bg-orange-50 text-orange-700"
                          : "bg-blue-50 text-blue-700"
                      }`}
                    >
                      {claim.status.replace("_", " ")}
                    </span>
                    <span className="text-sm text-slate-700 capitalize font-medium">
                      {claim.damage_type || "Processing"}
                    </span>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-xs text-slate-400">
                      {claim.created_at
                        ? new Date(claim.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })
                        : ""}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <div className="text-center py-10 text-slate-400">
              <TrendingUp className="w-8 h-8 mx-auto mb-2 opacity-40" />
              <p className="text-sm">No claims yet</p>
            </div>
          )}
        </div>

        {/* Quick Actions */}
        <div className="card p-6">
          <h2 className="text-base font-semibold text-slate-900 mb-5">Quick Actions</h2>
          <div className="space-y-3">
            {role === "claimant" && (
              <Link
                to="/claims/new"
                className="block p-4 rounded-lg border border-slate-100 hover:border-primary-200 hover:bg-primary-50/30 transition-all duration-150"
              >
                <p className="font-medium text-slate-900 text-sm">File a New Claim</p>
                <p className="text-xs text-slate-500 mt-1">
                  Upload damage photos for AI assessment
                </p>
              </Link>
            )}
            {(role === "assessor" || role === "admin") && (
              <>
                <Link
                  to="/review"
                  className="block p-4 rounded-lg border border-slate-100 hover:border-primary-200 hover:bg-primary-50/30 transition-all duration-150"
                >
                  <p className="font-medium text-slate-900 text-sm">Review Claims</p>
                  <p className="text-xs text-slate-500 mt-1">
                    {stats?.pending || 0} claims awaiting review
                  </p>
                </Link>
                <Link
                  to="/claims"
                  className="block p-4 rounded-lg border border-slate-100 hover:border-primary-200 hover:bg-primary-50/30 transition-all duration-150"
                >
                  <p className="font-medium text-slate-900 text-sm">All Claims</p>
                  <p className="text-xs text-slate-500 mt-1">
                    View complete claims history
                  </p>
                </Link>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
