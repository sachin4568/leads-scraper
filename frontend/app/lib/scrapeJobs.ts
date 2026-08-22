import { fetchWithAuth } from "./api";

export interface ScrapeJobPayload {
  niche: string;
  country?: string;
  region?: string;
  target_lead_count: number;
  sources?: string[];
}

export const scrapeJobsApi = {
  async create(payload: ScrapeJobPayload, token: string) {
    return fetchWithAuth("/scrape-jobs", { method: "POST", body: JSON.stringify(payload) }, token);
  },

  async list(token: string) {
    return fetchWithAuth("/scrape-jobs", { method: "GET" }, token);
  },

  async get(jobId: string, token: string) {
    return fetchWithAuth(`/scrape-jobs/${jobId}`, { method: "GET" }, token);
  },

  async stop(jobId: string, token: string) {
    return fetchWithAuth(`/scrape-jobs/${jobId}/stop-save`, { method: "POST" }, token);
  },

  async cancel(jobId: string, token: string) {
    return fetchWithAuth(`/scrape-jobs/${jobId}/cancel`, { method: "POST" }, token);
  },

  async resume(jobId: string, token: string) {
    return fetchWithAuth(`/scrape-jobs/${jobId}/resume`, { method: "POST" }, token);
  },

  connectWebSocket(jobId: string, token: string, onMessage: (msg: any) => void) {
    const ws = new WebSocket(`ws://localhost:8000/api/scrape-jobs/${jobId}/ws?token=${token}`);
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch (err) {
        console.error("WebSocket message parse error:", err);
      }
    };
    return ws;
  },
};
