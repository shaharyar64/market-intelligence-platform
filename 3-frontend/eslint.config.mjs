import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    // Not on by default in this eslint-config-next version, though the codebase
    // was written expecting it - there are eslint-disable comments for it. Two
    // bugs in one day came from a dependency array left short: a useMemo that
    // ignored the filter it was told to apply, and an effect that compared
    // against a list captured while it was still empty. Both are exactly what
    // this rule reports, and it finds only four things across the app.
    rules: { "react-hooks/exhaustive-deps": "warn" },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
