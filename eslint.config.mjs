import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import { globalIgnores } from "eslint/config";

const config = [
  globalIgnores([
    ".next/**",
    "node_modules/**",
    ".venv/**",
    "data/**",
    "coverage/**",
    "next-env.d.ts",
  ]),
  ...nextVitals,
  ...nextTs,
  { rules: { "react-hooks/set-state-in-effect": "off" } },
];

export default config;
