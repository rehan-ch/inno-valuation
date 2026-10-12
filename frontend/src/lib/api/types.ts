// Types for the InnoValuation API (/api/v1).
// Response and request types come from schema.d.ts, which `npm run gen:api` generates
// from openapi.json (the backend's OpenAPI schema). Do not hand-write API shapes here;
// add a one-line alias for each schema the frontend uses.
import type { components } from "./schema";

type Schemas = components["schemas"];

export type HealthOut = Schemas["HealthOut"];

// Hand-written on purpose: the backend's exception handlers return this envelope for
// every error, but no route declares it as a response model, so it is not in
// openapi.json yet. Keep it in line with backend/app/core/errors.py.
export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
  };
}
