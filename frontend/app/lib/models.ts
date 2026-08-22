import { fetchWithAuth } from "./api";

export const modelsApi = {
  async listVersions(token: string) {
    return fetchWithAuth("/models/versions", { method: "GET" }, token);
  },

  async train3Phase(token: string) {
    return fetchWithAuth("/models/train-3phase", { method: "POST" }, token);
  },

  async promote(version: string, token: string) {
    return fetchWithAuth(`/models/promote?version=${version}`, { method: "POST" }, token);
  },
};
