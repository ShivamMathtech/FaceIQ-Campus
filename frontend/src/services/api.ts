import { useQuery } from "@tanstack/react-query";
export type Row = Record<string, any>;
export interface User {
  id: string;
  name: string;
  email: string;
  role: "admin" | "faculty" | "student";
  active: boolean;
}
export interface Page<T = Row> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
}
let token = "";
export const setToken = (value: string) => {
  token = value;
};
export const getToken = () => token;
export async function api<T = Row>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", "Bearer " + token);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const res = await fetch("/api" + path, { ...options, headers });
  if (!res.ok) {
    let data;
    try {
      data = await res.json();
    } catch {
      data = { detail: res.statusText };
    }
    if (res.status === 401 && path != "/auth/login")
      window.dispatchEvent(new Event("session-expired"));
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail),
    );
  }
  return res.json();
}
export const post = <T = Row>(path: string, data?: unknown) =>
  api<T>(path, {
    method: "POST",
    body: data instanceof FormData ? data : JSON.stringify(data ?? {}),
  });
export const patch = (path: string, data: unknown) =>
  api(path, { method: "PATCH", body: JSON.stringify(data) });
export const remove = (path: string) => api(path, { method: "DELETE" });
export function useData<T = Row>(path: string, enabled = true) {
  return useQuery<T>({
    queryKey: [path],
    queryFn: () => api<T>(path),
    enabled,
    retry: 1,
    staleTime: 5000,
  });
}
export async function download(path: string, filename: string) {
  const r = await fetch("/api" + path, {
    headers: { Authorization: "Bearer " + token },
  });
  if (!r.ok) {
    const e = await r.json();
    throw new Error(e.detail ?? "Export failed");
  }
  const url = URL.createObjectURL(await r.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export const dateTime = (v: string) =>
  v
    ? new Date(
        v.endsWith("Z") || /[+-]\d\d:\d\d$/.test(v) ? v : v + "Z",
      ).toLocaleString()
    : "—";
export const localInput = (v: string) => {
  const d = new Date(v.endsWith("Z") ? v : v + "Z");
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
};
