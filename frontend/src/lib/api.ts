import axios, { AxiosError } from "axios";
import type { AuditData, AuditResponse } from "../types";

const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 20_000,
  headers: { "Content-Type": "application/json" },
});

export class ApiError extends Error {
  code: string;

  constructor(code: string, message: string) {
    super(message);
    this.code = code;
    this.name = "ApiError";
  }
}

/**
 * Runs an audit for the given URL against the Page Pulse backend.
 * Always throws ApiError on failure so callers can render a consistent,
 * structured error state instead of parsing raw axios errors.
 */
export async function auditUrl(url: string): Promise<AuditData> {
  try {
    const response = await client.post<AuditResponse>("/api/audit", { url });

    if (response.data.success) {
      return response.data.data;
    }

    throw new ApiError(response.data.error.code, response.data.error.message);
  } catch (error) {
    if (error instanceof ApiError) throw error;

    if (error instanceof AxiosError) {
      const payload = error.response?.data as AuditResponse | undefined;
      if (payload && payload.success === false) {
        throw new ApiError(payload.error.code, payload.error.message);
      }
      if (error.code === "ECONNABORTED") {
        throw new ApiError("TIMEOUT", "The request took too long to respond.");
      }
      throw new ApiError(
        "NETWORK_ERROR",
        "Could not reach the Page Pulse API. Is the backend running?"
      );
    }

    throw new ApiError("UNKNOWN_ERROR", "Something unexpected happened.");
  }
}
