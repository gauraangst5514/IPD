import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AuthState {
  token: string | null;
  userId: string | null;
  role: string | null;
  fullName: string | null;
  login: (token: string, userId: string, role: string, fullName: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      userId: null,
      role: null,
      fullName: null,
      login: (token, userId, role, fullName) =>
        set({ token, userId, role, fullName }),
      logout: () => set({ token: null, userId: null, role: null, fullName: null }),
    }),
    { name: "intelliclaim-auth" }
  )
);
