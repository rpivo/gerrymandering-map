// @ts-check
import js from "@eslint/js";
import astro from "eslint-plugin-astro";
import jsdoc from "eslint-plugin-jsdoc";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist/", ".astro/", "node_modules/"] },
  js.configs.recommended,
  ...tseslint.configs.strict,
  ...astro.configs.recommended,
  {
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    rules: {
      // CLAUDE.md: no function may exceed 100 lines, counting blank lines and comments.
      "max-lines-per-function": ["error", { max: 100, skipBlankLines: false, skipComments: false }],
    },
  },
  {
    // CLAUDE.md: exported functions need a docstring saying what they do and return.
    files: ["src/**/*.ts"],
    ignores: ["**/*.test.ts"],
    plugins: { jsdoc },
    rules: {
      "jsdoc/require-jsdoc": [
        "error",
        { publicOnly: true, require: { FunctionDeclaration: true, ArrowFunctionExpression: true } },
      ],
      "jsdoc/require-returns": "error",
      "jsdoc/require-param": "error",
    },
  },
);
