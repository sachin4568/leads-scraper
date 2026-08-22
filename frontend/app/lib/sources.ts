import { fetchWithAuth } from "./api";

export const sourcesApi = {
  async getHealth(token: string) {
    return fetchWithAuth("/sources/health", { method: "GET" }, token);
  },
};
