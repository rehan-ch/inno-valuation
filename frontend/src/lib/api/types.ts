// Response types for the InnoValuation API (/api/v1).
// Keep these in line with the Pydantic schemas in backend/app/schemas/.

export interface HealthOut {
  status: "ok";
  database: "ok" | "error";
  version: string;
}

export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
  };
}
