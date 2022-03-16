/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Based on https://github.com/hgrecco/pint/blob/master/pint/default_en.txt
 */

qx.Class.define("osparc.utils.Units", {
  type: "static",

  statics: {
    BASE_UNITS: {
      meter: {
        quantity: "length",
        alias: ["meter", "m", "metre"],
        short: "m",
        long: "meter"
      },
      second: {
        quantity: "time",
        alias: ["second", "s", "sec"],
        short: "s",
        long: "second"
      },
      ampere : {
        quantity: "current",
        alias: ["ampere", "A", "amp"],
        short: "A",
        long: "ampere"
      },
      candela: {
        quantity: "luminosity",
        alias: ["candela", "cd", "candle"],
        short: "cd",
        long: "candela"
      },
      gram: {
        quantity: "mass",
        alias: ["gram", "g"],
        short: "g",
        long: "gram"
      },
      mole: {
        quantity: "substance",
        alias: ["mole", "mol"],
        short: "mol",
        long: "mole"
      },
      kelvin: {
        quantity: "temperature",
        alias: ["kelvin", "K", "degK", "°K", "degree_Kelvin", "degreeK"],
        short: "K",
        long: "kelvin"
      },
      radian: {
        quantity: "radian",
        alias: ["radian", "rad"],
        short: "rad",
        long: "radian"
      },
      degree: {
        quantity: "angle",
        alias: ["degree", "deg"],
        short: "deg",
        long: "degree"
      }
    },

    PREFIXES: {
      "micro": "µ",
      "milli": "m",
      "null": null,
      "kilo": "k",
      "mega": "M"
    },

    __getBaseUnit: function(alias) {
      const baseUnits = Object.values(osparc.utils.Units.BASE_UNITS);
      for (const baseUnit of baseUnits) {
        if (baseUnit.alias.includes(alias)) {
          return baseUnit;
        }
      }
      return null;
    },

    getShortLabel: function(alias, prefix) {
      const baseUnit = this.__getBaseUnit(alias);
      let shortLabel = baseUnit ? baseUnit.short : alias;
      if (prefix && prefix in osparc.utils.Units.PREFIXES) {
        shortLabel = osparc.utils.Units.PREFIXES[prefix] + shortLabel;
      }
      return shortLabel;
    },

    getLongLabel: function(alias, prefix) {
      const baseUnit = this.__getBaseUnit(alias);
      let longLabel = baseUnit ? baseUnit.long : alias;
      if (prefix) {
        longLabel = prefix + longLabel;
      }
      return longLabel;
    },

    getPrefixShort: function(alias) {
      const baseUnit = this.__getBaseUnit(alias);
      return "prefixes" in baseUnit ? baseUnit["prefixes"] : [];
    },

    getPrefixLong: function() {

    }
  }
});
