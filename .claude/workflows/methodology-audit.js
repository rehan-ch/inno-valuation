// Dynamic workflow. Needs "Dynamic workflows" enabled (paid plans; on Pro turn it on in /config).
// Run with: /methodology-audit
// Fans out one auditor per scoring-related file, then one verifier that dedupes and ranks.
export const meta = {
  name: 'methodology-audit',
  description: 'Audit every file that computes or shows a score against docs/methodology/scoring-spec.md, then verify and rank the findings',
  phases: ['Find files', 'Audit', 'Verify'],
}

phase('Find files')
const found = await agent(
  'List every file in this repository that computes or displays a score, band, label, weight, priority, VfM or category total, or that contains an AI prompt or JSON schema. Look in backend/app/scoring, backend/app/services, backend/app/ai, backend/app/jobs, backend/app/schemas, backend/app/reports (PDF templates), and the frontend dashboard, assessment, compass and readiness components. Return relative paths only. Ignore docs and tests.',
  {
    schema: {
      type: 'object',
      required: ['files'],
      properties: { files: { type: 'array', items: { type: 'string' } } },
    },
  },
)

phase('Audit')
const audits = await pipeline(found.files, file =>
  agent(
    `Read docs/methodology/scoring-spec.md and docs/methodology/dimensions.yml first. Then audit ${file} for: invented rules (grades, risk score, aspect-count points, invented bands or tiers, hardcoded benchmarks); readiness and IQ values mixed; an LLM producing totals, bands, priorities, rankings or VfM; wrong formulas (IQ = sum/120*100, readiness dimension = sum of 5 answers, VfM = cost/IQ, bands as in the spec); PENDING rules without a "PROVISIONAL: see open-questions Qn" marker; dimension lists or question text hardcoded outside dimensions.yml. Return findings as {file, line, severity: "BLOCK" or "WARN", spec_section, problem, fix}. Return an empty list if the file is clean.`,
    {
      label: file,
      schema: {
        type: 'object',
        required: ['findings'],
        properties: { findings: { type: 'array', items: { type: 'object' } } },
      },
    },
  ),
)

phase('Verify')
const raw = audits.filter(Boolean).flatMap(a => a.findings)
log(`${raw.length} raw findings`)
const verified = await agent(
  `These are audit findings against docs/methodology/scoring-spec.md: ${JSON.stringify(raw)}. For each one, re-read the file at the line given and the spec section named, then decide: confirmed, false positive, or duplicate of another finding. Return only confirmed findings, deduplicated, sorted BLOCK first, each with the exact smallest fix. Finish with a two-line summary.`,
)
return verified
