import globals from "globals";
import path from "node:path";
import { fileURLToPath } from "node:url";
import js from "@eslint/js";
import { FlatCompat } from "@eslint/eslintrc";

// eslint-disable-next-line no-underscore-dangle
const __filename = fileURLToPath(import.meta.url);
// eslint-disable-next-line no-underscore-dangle
const __dirname = path.dirname(__filename);
const compat = new FlatCompat({
  baseDirectory: __dirname,
  recommendedConfig: js.configs.recommended,
  allConfig: js.configs.all
});

export default [...compat.extends("qx"), {
  languageOptions: {
    globals: {
      ...globals.browser,
      qx: false,
      q: false,
      qxWeb: false,
      osparc: false,
      explorer: false,
      Ajv: false,
      objectPath: false,
    },

    ecmaVersion: 2017,
    sourceType: "script",
  },

  rules: {
    camelcase: ["error", {
      properties: "always",
    }],

    "no-underscore-dangle": ["error", {
      allowAfterThis: true,
      enforceInMethodNames: false,
    }],

    "no-warning-comments": "off",
    "no-confusing-arrow": "off",
    "object-curly-newline": "off",

    "newline-per-chained-call": ["error", {
      ignoreChainWithDepth: 3,
    }],

    "no-eq-null": 0,
    semi: "off",
    "comma-dangle": "off",
    "object-curly-spacing": "off",
    "no-implicit-coercion": "off",
    "arrow-body-style": "off",
  },
}];
