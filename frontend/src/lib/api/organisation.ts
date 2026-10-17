// /api/v1/organisation(s): create an organisation, and read or edit the active one.
import { getJson, patchJson, postJson } from "./client";
import type { OrganisationCreateIn, OrganisationOut, OrganisationUpdateIn } from "./types";

export function createOrganisation(input: OrganisationCreateIn): Promise<OrganisationOut> {
  return postJson("/organisations", input);
}

export function getOrganisation(init?: RequestInit): Promise<OrganisationOut> {
  return getJson("/organisation", init);
}

export function updateOrganisation(input: OrganisationUpdateIn): Promise<OrganisationOut> {
  return patchJson("/organisation", input);
}
