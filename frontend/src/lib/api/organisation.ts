// /api/v1/organisation(s): create an organisation and read the active one.
import { getJson, postJson } from "./client";
import type { OrganisationCreateIn, OrganisationOut } from "./types";

export function createOrganisation(input: OrganisationCreateIn): Promise<OrganisationOut> {
  return postJson("/organisations", input);
}

export function getOrganisation(init?: RequestInit): Promise<OrganisationOut> {
  return getJson("/organisation", init);
}
