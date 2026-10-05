// Dynamic workflow. Needs "Dynamic workflows" enabled (paid plans; on Pro turn it on in /config).
// Run with: /dimension-content-check
// Requires the book text at reference/book.txt (pdftotext output of the 12 Dimensions book).
// One agent per dimension checks questions, next steps and sub-aspects in dimensions.yml against the book.
export const meta = {
  name: 'dimension-content-check',
  description: 'Verify every dimension in docs/methodology/dimensions.yml against the book text in reference/book.txt, one agent per dimension',
  phases: ['Load', 'Check', 'Report'],
}

phase('Load')
const loaded = await agent(
  'Read docs/methodology/dimensions.yml and return the list of dimension keys in order. Also confirm whether reference/book.txt exists.',
  {
    schema: {
      type: 'object',
      required: ['keys', 'book_exists'],
      properties: {
        keys: { type: 'array', items: { type: 'string' } },
        book_exists: { type: 'boolean' },
      },
    },
  },
)

if (!loaded.book_exists) {
  return 'reference/book.txt not found. Run: pdftotext -layout "12_Dimensions_of_Innovation.pdf" reference/book.txt'
}

phase('Check')
const results = await pipeline(loaded.keys, key =>
  agent(
    `Compare the dimension with key "${key}" in docs/methodology/dimensions.yml against reference/book.txt. Use Chapter 15 for the five readiness questions and the "Next Steps" sentence, and the dimension's own chapter (Chapters 1 to 12) for the sub-aspect headings. Report every wording difference, missing item or extra item. Ignore straight versus curly quotes. Return {key, ok, differences: [{field, in_yaml, in_book}]}.`,
    {
      label: key,
      schema: {
        type: 'object',
        required: ['key', 'ok', 'differences'],
        properties: {
          key: { type: 'string' },
          ok: { type: 'boolean' },
          differences: { type: 'array', items: { type: 'object' } },
        },
      },
    },
  ),
)

phase('Report')
const problems = results.filter(Boolean).filter(r => !r.ok)
log(`${problems.length} of ${loaded.keys.length} dimensions have differences`)
return problems
