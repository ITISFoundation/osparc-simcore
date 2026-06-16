/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Tobias Oetiker (oetiker)
     * Odei Maiz (odeimaiz)
     * Ignacio Pascual (ignapas)

************************************************************************ */

qx.Theme.define("osparc.theme.osparcportal.Font", {
  extend: osparc.theme.common.Font,

  fonts: {
    "default": {
      size: 13,
      family: ["sans-serif"],
      color: "text",
      sources: [
        {
          family: "Asap",
          source: [
            "osparc/theme/font/Asap/Asap-Regular.ttf"
          ]
        }
      ]
    },

    "bold": {
      size: 13,
      family: ["sans-serif"],
      bold: true,
      color: "text",
      sources: [
        {
          family: "Asap",
          source: [
            "osparc/theme/font/Asap/Asap-Bold.ttf"
          ]
        }
      ]
    },

    "headline": {
      size: 24,
      family: ["sans-serif"],
      color: "text",
      sources: [
        {
          family: "Asap",
          source: [
            "osparc/theme/font/Asap/Asap-Regular.ttf"
          ]
        }
      ]
    },

    "monospace": {
      size: 14,
      family: ["monospace"],
      color: "text",
      sources: [
        {
          family: "Asap Mono",
          source: [
            "osparc/theme/font/Asap/Asap-Regular.ttf"
          ]
        }
      ]
    },

    "nav-bar-label": {
      size: 20,
      family: ["Asap"],
      color: "text",
      bold: true
    },

    "title-18": {
      size: 18,
      family: ["Asap"],
      color: "text",
      bold: true
    },

    "text-18": {
      size: 18,
      family: ["Asap"],
      color: "text"
    },

    "title-16": {
      size: 16,
      family: ["Asap"],
      color: "text",
      bold: true
    },

    "text-16": {
      size: 16,
      family: ["Asap"],
      color: "text"
    },

    "title-14": {
      size: 14,
      family: ["Asap"],
      color: "text",
      bold: true
    },

    "text-14": {
      size: 14,
      family: ["Asap"],
      color: "text"
    },

    "title-13": {
      size: 13,
      family: ["Asap", "sans-serif"],
      color: "text",
      bold: true
    },

    "text-13": {
      size: 13,
      family: ["Asap", "sans-serif"],
      color: "text"
    },

    "title-12": {
      size: 12,
      family: ["Asap"],
      color: "text",
      bold: true
    },

    "text-12": {
      size: 12,
      family: ["Asap"],
      color: "text"
    },

    "link-label": {
      size: 12,
      family: ["Asap"],
      color: "text-darker",
      decoration: "underline"
    },

    "text-12-italic": {
      size: 12,
      family: ["Asap"],
      color: "text",
      italic: true
    },

    "text-11": {
      size: 11,
      family: ["Asap"],
      color: "text"
    },

    "text-10": {
      size: 10,
      family: ["Asap"],
      color: "text"
    },

    "text-9": {
      size: 9,
      family: ["Asap"],
      color: "text"
    },

    "text-8-italic": {
      size: 8,
      family: ["Asap"],
      color: "text",
      italic: true
    },

    "workbench-start-hint": {
      size: 20,
      family: ["Asap"],
      color: "text-disabled",
      bold: true
    },

    "workbench-io-label": {
      size: 20,
      family: ["monospace"],
      color: "text-disabled",
      bold: true
    }
  }
});
