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
      micro: {
        short: "µ",
        long: "micro"
      },
      milli: {
        short: "m",
        long: "milli"
      },
      "no-prefix": {
        short: "",
        long: ""
      },
      kilo: {
        short: "k",
        long: "kilo"
      },
      mega: {
        short: "M",
        long: "mega"
      }
    },

    __getBaseUnit: function(unitKey) {
      return unitKey in osparc.utils.Units.BASE_UNITS ? osparc.utils.Units.BASE_UNITS[unitKey] : null;
    },

    getShortLabel: function(unit, prefix) {
      const baseUnit = this.__getBaseUnit(unit);
      let shortLabel = baseUnit ? baseUnit.short : unit;
      if (prefix && prefix in osparc.utils.Units.PREFIXES) {
        shortLabel = osparc.utils.Units.PREFIXES[prefix].short + shortLabel;
      }
      return shortLabel;
    },

    getLongLabel: function(unit, prefix) {
      const baseUnit = this.__getBaseUnit(unit);
      let longLabel = baseUnit ? baseUnit.long : unit;
      if (prefix && prefix in osparc.utils.Units.PREFIXES) {
        longLabel = osparc.utils.Units.PREFIXES[prefix].long + longLabel;
      }
      return longLabel;
    },

    getNextPrefix: function(prefix) {
      if ([null, undefined, ""].includes(prefix)) {
        prefix = "no-prefix";
      }
      const keys = Object.keys(osparc.utils.Units.PREFIXES);
      const idx = keys.indexOf(prefix);
      if (idx === -1) {
        return null;
      }
      if (idx === keys.length-1) {
        return osparc.utils.Units.PREFIXES[keys[0]];
      }
      return osparc.utils.Units.PREFIXES[keys[idx+1]];
    }
  }
});
