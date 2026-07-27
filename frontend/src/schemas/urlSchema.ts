import { z } from "zod";

export const urlAuditSchema = z.object({
  url: z
    .string()
    .trim()
    .min(1, "Enter a URL to audit.")
    .refine((value) => {
      try {
        const parsed = new URL(value);
        return parsed.protocol === "http:" || parsed.protocol === "https:";
      } catch {
        return false;
      }
    }, "Enter a full URL starting with http:// or https://"),
});

export type UrlAuditFormValues = z.infer<typeof urlAuditSchema>;
