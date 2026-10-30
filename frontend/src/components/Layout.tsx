import { Outlet, Link, useLocation } from "react-router-dom";
import { useAuthStore } from "../store/auth";
import {
  LayoutDashboard,
  FileText,
  PlusCircle,
  ClipboardCheck,
  LogOut,
  Shield,
  ChevronRight,
} from "lucide-react";

const navItems = [
  { path: "/retrieval", label: "Photo Retrieval", icon: Shield, roles: ["assessor", "admin"] },
  { path: "/evidence", label: "Evidence Graph", icon: Shield, roles: ["assessor", "admin"] },
  { path: "/", label: "Dashboard", icon: LayoutDashboard, roles: ["claimant", "assessor", "admin"] },
  { path: "/claims", label: "My Claims", icon: FileText, roles: ["claimant"] },
  { path: "/claims/new", label: "New Claim", icon: PlusCircle, roles: ["claimant"] },
  { path: "/review", label: "Review Queue", icon: ClipboardCheck, roles: ["assessor", "admin"] },
  { path: "/claims", label: "All Claims", icon: FileText, roles: ["assessor", "admin"] },
];

export default function Layout() {
  const { fullName, role, logout } = useAuthStore();
  const location = useLocation();

  const visibleNav = navItems.filter((item) => item.roles.includes(role || ""));

  // Breadcrumb
  const pathSegments = location.pathname.split("/").filter(Boolean);
  const breadcrumbs = pathSegments.map((seg, i) => ({
    label: seg.charAt(0).toUpperCase() + seg.slice(1).replace(/-/g, " "),
    path: "/" + pathSegments.slice(0, i + 1).join("/"),
  }));

  return (
    <div className="flex h-screen bg-slate-50">
      {/* Sidebar */}
      <aside className="w-[260px] bg-brand-sidebar flex flex-col shadow-lg">
        {/* Logo */}
        <div className="px-6 py-5">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-primary-500 rounded-lg flex items-center justify-center">
              <Shield className="w-4.5 h-4.5 text-white" />
            </div>
            <div>
              <h1 className="text-[15px] font-bold text-white tracking-tight">IntelliClaim</h1>
              <p className="text-[10px] text-slate-400 font-medium tracking-wide uppercase">AI Insurance Platform</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 mt-2 space-y-0.5">
          <p className="px-3 py-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
            Menu
          </p>
          {visibleNav.map((item) => {
            const isActive = location.pathname === item.path;
            const Icon = item.icon;
            return (
              <Link
                key={item.path + item.label}
                to={item.path}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13px] font-medium transition-all duration-150 ${
                  isActive
                    ? "bg-primary-600/20 text-white"
                    : "text-slate-300 hover:bg-white/5 hover:text-white"
                }`}
              >
                <Icon className={`w-[18px] h-[18px] ${isActive ? "text-primary-400" : ""}`} />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* User section */}
        <div className="px-4 py-4 border-t border-white/10">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-primary-600/30 flex items-center justify-center">
              <span className="text-sm font-semibold text-primary-300">
                {fullName?.charAt(0).toUpperCase()}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">{fullName}</p>
              <p className="text-[11px] text-slate-400 capitalize">{role}</p>
            </div>
          </div>
          <button
            onClick={logout}
            className="flex items-center gap-2 mt-3 w-full px-3 py-2 rounded-lg text-[12px] text-slate-400 hover:text-red-400 hover:bg-white/5 transition-colors"
          >
            <LogOut className="w-3.5 h-3.5" />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header className="h-14 bg-white border-b border-slate-200/80 flex items-center px-8 shadow-sm">
          <nav className="flex items-center gap-1 text-sm text-slate-500">
            <Link to="/" className="hover:text-primary-600 transition-colors">Home</Link>
            {breadcrumbs.map((crumb, i) => (
              <span key={crumb.path} className="flex items-center gap-1">
                <ChevronRight className="w-3.5 h-3.5" />
                {i === breadcrumbs.length - 1 ? (
                  <span className="text-slate-900 font-medium">{crumb.label}</span>
                ) : (
                  <Link to={crumb.path} className="hover:text-primary-600 transition-colors">
                    {crumb.label}
                  </Link>
                )}
              </span>
            ))}
          </nav>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
