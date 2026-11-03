"use strict";

// Shared ESLint configuration for the qooxdoo clients. It exists only to run the
// CI gate in .github/workflows/client-eslint.yml (`npm run linter`); the client
// itself is compiled through the qooxdoo-kit image with its own linter settings
// (see services/static-webserver/client/compile.json).

const qxBrowserConfig = require("@qooxdoo/eslint-config-qx/browser");
const qxPlugin = require("@qooxdoo/eslint-plugin-qx");
const globals = require("globals");

// Formatting rules were deprecated in ESLint 8.53 and are removed from the core in v11,
// so they are not worth re-baselining the client on. They are switched off here instead
// of being migrated to @stylistic/eslint-plugin.
const STYLISTIC_RULES = [
    "arrow-body-style", "arrow-parens", "arrow-spacing", "block-spacing", "brace-style",
    "comma-dangle", "comma-spacing", "comma-style", "computed-property-spacing",
    "dot-location", "eol-last", "generator-star-spacing", "indent", "jsx-quotes",
    "key-spacing", "keyword-spacing", "linebreak-style", "lines-around-comment", "max-len",
    "max-statements-per-line", "new-parens", "newline-per-chained-call", "no-confusing-arrow",
    "no-extra-parens", "no-extra-semi", "no-floating-decimal", "no-mixed-operators",
    "no-mixed-spaces-and-tabs", "no-multi-spaces", "no-multiple-empty-lines",
    "no-trailing-spaces", "no-whitespace-before-property", "object-curly-newline",
    "object-curly-spacing", "object-property-newline", "one-var-declaration-per-line",
    "operator-linebreak", "padded-blocks", "quote-props", "quotes", "rest-spread-spacing",
    "semi", "semi-spacing", "space-before-blocks", "space-before-function-paren",
    "space-in-parens", "space-infix-ops", "space-unary-ops", "switch-colon-spacing",
    "template-curly-spacing", "template-tag-spacing", "wrap-iife", "yield-star-spacing",
];

module.exports = [
    {
        ignores: [
            "services/static-webserver/client/source/resource/",
            "services/static-webserver/client/source-output/",
        ],
    },
    ...qxBrowserConfig,
    {
        languageOptions: {
            globals: {
                // the qx browser preset only declares a handful of them
                ...globals.browser,
                ...globals.es2024,
                osparc: "readonly",
                explorer: "readonly",
                Ajv: "readonly",
                objectPath: "readonly",
            },
        },
        plugins: {
            // same plugin as "@qooxdoo/qx" above, registered under the key used by the
            // inline disable comments in the client sources
            "qx-rules": qxPlugin,
        },
        rules: {
            ...Object.fromEntries(STYLISTIC_RULES.map(rule => [rule, "off"])),
            "@qooxdoo/qx/no-refs-in-members": "off",
            "qx-rules/no-refs-in-members": "error",
            // rules the clients had configured before moving to the @qooxdoo preset
            "block-scoped-var": "warn",
            "camelcase": ["error", {"properties": "always"}],
            "curly": ["warn", "all"],
            "new-cap": "off",
            "no-console": "off",
            "no-constant-condition": ["error", {"checkLoops": false}],
            "no-dupe-class-members": "warn",
            "no-dupe-keys": "warn",
            "no-eq-null": "off",
            "no-implicit-coercion": "off",
            "no-underscore-dangle": ["error", {
                "allowAfterThis": true,
                "enforceInMethodNames": false,
            }],
            "no-unused-vars": ["warn", {"args": "none"}],
            "no-warning-comments": "off",
        },
    },
];
