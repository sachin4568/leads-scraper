import { fetchWithAuth } from "./api";

export const leadsApi = {
  async list(token: string) {
    return fetchWithAuth("/leads", { method: "GET" }, token);
  },

  async qualify(leadId: string, token: string) {
    return fetchWithAuth(`/leads/${leadId}/qualify`, { method: "POST" }, token);
  },

  async submitFeedback(leadId: string, payload: { rating: string; service_label?: string; comments?: string }, token: string) {
    return fetchWithAuth(`/leads/${leadId}/feedback`, { method: "POST", body: JSON.stringify(payload) }, token);
  },

  async delete(leadId: string, token: string) {
    return fetchWithAuth(`/leads/${leadId}`, { method: "DELETE" }, token);
  },
};
