"use client";

import { useState, useEffect, useCallback, createContext, useContext } from "react";

interface ToastState {
  message: string;
  type: "success" | "error";
}

interface ToastContextType {
  showToast: (message: string, type?: "success" | "error") => void;
}

const ToastContext = createContext<ToastContextType | null>(null);

// 全局 toast 方法，供 api.ts 调用
let globalShowToast: ((message: string, type?: "success" | "error") => void) | null = null;

export function toast(message: string, type: "success" | "error" = "error") {
  if (globalShowToast) {
    globalShowToast(message, type);
  }
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast must be used within ToastProvider");
  return context;
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<ToastState | null>(null);

  const showToast = useCallback((message: string, type: "success" | "error" = "error") => {
    setState({ message, type });
  }, []);

  useEffect(() => {
    globalShowToast = showToast;
    return () => { globalShowToast = null; };
  }, [showToast]);

  useEffect(() => {
    if (state) {
      const timer = setTimeout(() => setState(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [state]);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      {state && (
        <div
          className={`fixed top-4 left-1/2 -translate-x-1/2 z-50 px-6 py-3 rounded-lg shadow-lg text-white text-sm transition-all ${
            state.type === "error" ? "bg-red-500" : "bg-green-500"
          }`}
        >
          {state.message}
        </div>
      )}
    </ToastContext.Provider>
  );
}
