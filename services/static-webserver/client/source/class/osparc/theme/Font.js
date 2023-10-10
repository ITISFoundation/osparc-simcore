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

************************************************************************ */

qx.Theme.define("osparc.theme.Font", {
  extend: osparc.theme.common.Font,

  fonts: {
    "defaults": {
      family: ["sans-serif"],
      color: "text",
      sources: [
        {
          family: "Manrope",
          source: [
            "common/Manrope/Manrope-VariableFont_wght.ttf"
          ]
        }
      ]
    },

    "default": {
      include: "defaults",
      size: 13
    },

    "title-18": {
      include: "defaults",
      size: 18,
      bold: true
    },

    "text-18": {
      include: "defaults",
      size: 18
    },

    "title-16": {
      include: "defaults",
      size: 16,
      bold: true
    },

    "text-16": {
      include: "defaults",
      size: 16
    },

    "title-14": {
      include: "defaults",
      size: 14,
      bold: true
    },

    "text-14": {
      include: "defaults",
      size: 14
    },

    "link-label-14": {
      include: "defaults",
      size: 14,
      color: "text-darker",
      decoration: "underline"
    },

    "text-13": {
      include: "defaults",
      size: 13
    },

    "text-12": {
      include: "defaults",
      size: 12
    },

    "link-label-12": {
      include: "defaults",
      size: 12,
      color: "text-darker",
      decoration: "underline"
    },

    "text-11": {
      include: "defaults",
      size: 11
    },

    "text-11-italic": {
      include: "defaults",
      size: 11,
      italic: true
    },

    "text-10": {
      include: "defaults",
      size: 10
    },

    "text-9": {
      include: "defaults",
      size: 9
    },

    "workbench-start-hint": {
      include: "defaults",
      size: 20,
      color: "workbench-start-hint",
      bold: true
    }
  }
});
