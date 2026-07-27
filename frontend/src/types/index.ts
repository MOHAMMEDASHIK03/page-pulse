export interface AuditData {
  url: string;
  final_url: string;
  status_code: number | null;
  response_time_ms: number | null;
  https: boolean;
  title: string | null;
  meta_description: string | null;
  content_type: string | null;
  server: string | null;
  content_length: number | null;
  timestamp: string;
  cached: boolean;
}

export interface AuditSuccessResponse {
  success: true;
  data: AuditData;
}

export interface ApiErrorDetail {
  code: string;
  message: string;
}

export interface AuditErrorResponse {
  success: false;
  error: ApiErrorDetail;
}

export type AuditResponse = AuditSuccessResponse | AuditErrorResponse;
