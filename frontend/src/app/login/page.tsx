"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { LogIn, UserPlus, Mail, Lock, Building2, Briefcase } from "lucide-react";
import { api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("farmer");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    setSuccess("");

    try {
      let result;
      if (mode === "login") {
        result = await api.login(email, password);
      } else {
        result = await api.register(email, password, company, role);
      }

      // Store token
      localStorage.setItem("openclaw_token", result.token);
      localStorage.setItem("openclaw_user", JSON.stringify(result.user));

      setSuccess(`Welcome, ${result.user.email}! Tier: ${result.user.tier}`);

      // Redirect to dashboard after brief delay
      setTimeout(() => {
        router.push("/");
      }, 1000);
    } catch (err: any) {
      setError(err?.message || "Authentication failed");
    }
    setLoading(false);
  };

  return (
    <div className="min-h-[80vh] flex items-center justify-center">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md"
      >
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-ocean-500 to-ocean-600 flex items-center justify-center mx-auto mb-4 shadow-[0_0_32px_rgba(0,212,200,0.3)]">
            <span className="text-white font-bold text-2xl">OC</span>
          </div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">FishIntel</h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">Aquaculture Intelligence Platform</p>
        </div>

        {/* Tab Toggle */}
        <div className="flex mb-6 bg-white/[0.04] rounded-xl p-1 border border-white/[0.06]">
          <button
            onClick={() => setMode("login")}
            className={`flex-1 py-2.5 rounded-lg text-sm font-medium transition-all ${
              mode === "login"
                ? "bg-ocean-500/15 text-ocean-400 border border-ocean-500/20"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            <LogIn className="w-4 h-4 inline mr-2" />
            Sign In
          </button>
          <button
            onClick={() => setMode("register")}
            className={`flex-1 py-2.5 rounded-lg text-sm font-medium transition-all ${
              mode === "register"
                ? "bg-ocean-500/15 text-ocean-400 border border-ocean-500/20"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            <UserPlus className="w-4 h-4 inline mr-2" />
            Register
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-[11px] text-[var(--text-secondary)] uppercase tracking-wider mb-1 block">Email</label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-secondary)]" />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="you@company.com"
                className="w-full pl-10 pr-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-sm text-[var(--text-primary)] placeholder:text-white/20 focus:outline-none focus:border-ocean-500/30 transition-colors"
              />
            </div>
          </div>

          <div>
            <label className="text-[11px] text-[var(--text-secondary)] uppercase tracking-wider mb-1 block">Password</label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-secondary)]" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
                placeholder="Min. 6 characters"
                className="w-full pl-10 pr-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-sm text-[var(--text-primary)] placeholder:text-white/20 focus:outline-none focus:border-ocean-500/30 transition-colors"
              />
            </div>
          </div>

          {mode === "register" && (
            <>
              <div>
                <label className="text-[11px] text-[var(--text-secondary)] uppercase tracking-wider mb-1 block">Company</label>
                <div className="relative">
                  <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-secondary)]" />
                  <input
                    type="text"
                    value={company}
                    onChange={(e) => setCompany(e.target.value)}
                    placeholder="Your company name"
                    className="w-full pl-10 pr-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-sm text-[var(--text-primary)] placeholder:text-white/20 focus:outline-none focus:border-ocean-500/30 transition-colors"
                  />
                </div>
              </div>

              <div>
                <label className="text-[11px] text-[var(--text-secondary)] uppercase tracking-wider mb-1 block">I am a</label>
                <div className="relative">
                  <Briefcase className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-secondary)]" />
                  <select
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    className="w-full pl-10 pr-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none focus:border-ocean-500/30 transition-colors appearance-none"
                  >
                    <option value="farmer">Salmon Farmer</option>
                    <option value="buyer">Buyer / Processor</option>
                    <option value="trader">Trader / Analyst</option>
                    <option value="investor">Investor</option>
                  </select>
                </div>
              </div>
            </>
          )}

          {error && (
            <div className="p-3 rounded-xl bg-rose-500/[0.08] border border-rose-500/20 text-rose-400 text-sm">
              {error}
            </div>
          )}

          {success && (
            <div className="p-3 rounded-xl bg-emerald-500/[0.08] border border-emerald-500/20 text-emerald-400 text-sm">
              {success}
            </div>
          )}

          <motion.button
            type="submit"
            disabled={loading}
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.99 }}
            className="w-full py-3 rounded-xl bg-gradient-to-r from-ocean-500 to-ocean-600 text-white font-semibold text-sm shadow-[0_0_20px_rgba(0,212,200,0.2)] hover:shadow-[0_0_30px_rgba(0,212,200,0.3)] transition-all disabled:opacity-50"
          >
            {loading ? "..." : mode === "login" ? "Sign In" : "Create Account"}
          </motion.button>
        </form>

        <p className="text-[10px] text-[var(--text-secondary)] text-center mt-6 opacity-50">
          Free tier includes Dashboard, Morning Brief, and basic lice data.
          Upgrade anytime for full access.
        </p>
      </motion.div>
    </div>
  );
}
