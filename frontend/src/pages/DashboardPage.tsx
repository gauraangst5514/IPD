import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "../store/auth";
import { FileText, AlertTriangle, CheckCircle, Clock } from "lucide-react";
import api from "../lib/api";

export default function DashboardPage() {
  const { fullName, role } = useAuthStore();

  const { data: stats } = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: () => api.get("/stats").then((r) => r.data),
  });

  const statCards = [
    { label: "Total Claims", value: stats?.total ?? "–", icon: FileText, color: "text-blue-600 bg-blue-50" },
    { label: "Pending Review", value: stats?.pending ?? "–", icon: Clock, color: "text-yellow-600 bg-yellow-50" },
    { label: "Approved", value: stats?.approved ?? "–", icon: CheckCircle, color: "text-green-600 bg-green-50" },
    { label: "Flagged", value: stats?.flagged ?? "–", icon: AlertTriangle, color: "text-red-600 bg-red-50" },
  ];

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">
          Welcome back, {fullName}
        </h1>
        <p className="text-gray-600 mt-1">
          {role === "claimant" && "Manage your insurance claims and track their status."}
          {role === "assessor" && "Review and assess pending insurance claims."}
          {role === "admin" && "System overview and management."}
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {statCards.map((stat) => {
          const Icon = stat.icon;
          return (
            <div
              key={stat.label}
              className="bg-white rounded-xl border border-gray-200 p-6"
            >
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-lg ${stat.color}`}>
                  <Icon className="w-5 h-5" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-gray-900">{stat.value}</p>
                  <p className="text-sm text-gray-500">{stat.label}</p>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Quick Actions */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h2>
        <div className="space-y-3">
          {role === "claimant" && (
            <a
              href="/claims/new"
              className="block p-4 border border-gray-200 rounded-lg hover:border-primary-300 hover:bg-primary-50 transition-colors"
            >
              <p className="font-medium text-gray-900">File a New Claim</p>
              <p className="text-sm text-gray-500">
                Upload photos of vehicle damage and get an AI-powered assessment
              </p>
            </a>
          )}
          {(role === "assessor" || role === "admin") && (
            <a
              href="/review"
              className="block p-4 border border-gray-200 rounded-lg hover:border-primary-300 hover:bg-primary-50 transition-colors"
            >
              <p className="font-medium text-gray-900">Review Claims</p>
              <p className="text-sm text-gray-500">
                View AI assessments, heatmaps, and fraud scores for pending claims
              </p>
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
