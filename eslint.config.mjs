import babelParser from "babel-eslint";
import path from "node:path";
import { fileURLToPath } from "node:url";
import js from "@eslint/js";
import { FlatCompat } from "@eslint/eslintrc";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const compat = new FlatCompat({
  baseDirectory: __dirname,
  recommendedConfig: js.configs.recommended,
  allConfig: js.configs.all
});

export default [{
  ignores: [
    "services/web/client/source/resource/",
    "services/web/client/contrib/",
    "services/web/client/source-output/",
    "services/*node_modules/",
    "services/dy-modeling/client/source/resource/",
    "services/dy-modeling/client/source-output/",
    "services/dy-modeling/server/source/thrift/",
  ],
}, ...compat.extends("eslint:recommended"), {
  languageOptions: {
    globals: {
      osparc: false,
      window: false,
    },

    parser: babelParser,
  },

  rules: {
    "max-len": [2, 150],
    "new-cap": "off",
    "require-jsdoc": "off",
    "linebreak-style": ["error", "unix"],
    curly: ["warn", "all"],
    "block-scoped-var": "warn",
    "brace-style": ["warn", "1tbs"],

    indent: ["warn", 2, {
      SwitchCase: 1,
    }],

    "object-property-newline": "warn",

    "object-curly-newline": ["warn", {
      ObjectExpression: {
        multiline: true,
        minProperties: 1,
      },

      ObjectPattern: {
        multiline: true,
        minProperties: 3,
      },
    }],

    "key-spacing": ["warn", {
      singleLine: {
        beforeColon: false,
        afterColon: true,
      },

      multiLine: {
        beforeColon: false,
        afterColon: true,
      },
    }],

    "no-dupe-keys": "warn",
    "no-dupe-class-members": "warn",

    "no-unused-vars": ["warn", {
      args: "none",
    }],
  },
}];