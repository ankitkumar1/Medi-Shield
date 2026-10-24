const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export function api(path) {
  return `${API}${path}`;
}

export async function getJSON(path) {
  const response = await fetch(api(path), { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json();
}
