import { Outlet, Link, useLocation } from "react-router-dom";
import { useAuthStore } from "../store/auth";
import {
  LayoutDashboard,
  FileText,
  PlusCircle,
  ClipboardCheck,
  LogOut,
  Shield,
} from "lucide-react";

const navItems = [
  { path: "/", label: "Dashboard", icon: LayoutDashboard, roles: ["claimant", "assessor", "admin"] },
  { path: "/claims", label: "My Claims", icon: FileText, roles: ["claimant"] },
  { path: "/claims/new", label: "New Claim", icon: PlusCircle, roles: ["claimant"] },
  { path: "/review", label: "Review Queue", icon: ClipboardCheck, roles: ["assessor", "admin"] },
];

export default function Layout() {
  const { fullName, role, logout } = useAuthStore();
  const location = useLocation();

  const visibleNav = navItems.filter((item) => item.roles.includes(role || ""));

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <Shield className="w-6 h-6 text-primary-600" />
            <h1 className="text-xl font-bold text-gray-900">IntelliClaim</h1>
          </div>
          <p className="text-xs text-gray-500 mt-1">AI Insurance Assessment</p>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          {visibleNav.map((item) => {
            const isActive = location.pathname === item.path;
            const Icon = item.icon;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? "bg-primary-50 text-primary-700 font-medium"
                    : "text-gray-600 hover:bg-gray-100"
                }`}
              >
                <Icon className="w-4 h-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="p-4 border-t border-gray-200">
          <div className="text-sm font-medium text-gray-900">{fullName}</div>
          <div className="text-xs text-gray-500 capitalize">{role}</div>
          <button
            onClick={logout}
            className="flex items-center gap-2 mt-3 text-sm text-red-600 hover:text-red-700"
          >
            <LogOut className="w-4 h-4" />
            Logout
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto p-8">
        <Outlet />
      </main>
    </div>
  );
}
