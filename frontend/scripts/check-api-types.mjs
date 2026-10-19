// Fails when src/lib/api/schema.d.ts is not what openapi.json generates.
// Regenerates into a temp file with the same CLI and options as `npm run gen:api`,
// so the comparison is byte for byte.
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const committedPath = join(root, "src/lib/api/schema.d.ts");
const require = createRequire(import.meta.url);
const cliPath = join(
  dirname(require.resolve("openapi-typescript/package.json")),
  "bin/cli.js",
);

const tempDir = mkdtempSync(join(tmpdir(), "innovaluation-api-types-"));
const freshPath = join(tempDir, "schema.d.ts");
const regenerate = "Run 'npm run gen:api' in frontend/ and commit src/lib/api/schema.d.ts.";

function readOrNull(path) {
  try {
    return readFileSync(path, "utf8");
  } catch {
    return null;
  }
}

try {
  execFileSync(process.execPath, [cliPath, join(root, "openapi.json"), "-o", freshPath], {
    stdio: ["ignore", "ignore", "inherit"],
  });
  const committed = readOrNull(committedPath);
  if (committed === null) {
    console.error(`API types are missing: src/lib/api/schema.d.ts. ${regenerate}`);
    process.exitCode = 1;
  } else if (readFileSync(freshPath, "utf8") !== committed) {
    console.error(`API types are stale: schema.d.ts does not match openapi.json. ${regenerate}`);
    process.exitCode = 1;
  } else {
    console.log("API types match openapi.json.");
  }
} finally {
  rmSync(tempDir, { recursive: true, force: true });
}
