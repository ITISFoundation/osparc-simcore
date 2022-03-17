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
      "degree_Celsius": {
        quantity: "temperature",
        alias: ["degree_Celsius", "°C"],
        short: "°C",
        long: "Degree Celsius"
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
        long: "micro",
        multiplier: 1e-6
      },
      milli: {
        short: "m",
        long: "milli",
        multiplier: 1e-3
      },
      "no-prefix": {
        short: "",
        long: "",
        multiplier: 1e0
      },
      kilo: {
        short: "k",
        long: "kilo",
        multiplier: 1e3
      },
      mega: {
        short: "M",
        long: "mega",
        multiplier: 1e6
      }
    },

    __getBaseUnit: function(unitKey) {
      return unitKey in this.BASE_UNITS ? this.BASE_UNITS[unitKey] : null;
    },

    getLabels: function(unit, prefix) {
      return {
        unitShort: this.__getShortLabel(unit, prefix),
        unitLong: this.__getLongLabel(unit, prefix)
      };
    },

    __getShortLabel: function(unit, prefix) {
      const baseUnit = this.__getBaseUnit(unit);
      let shortLabel = baseUnit ? baseUnit.short : unit;
      if (prefix && prefix in this.PREFIXES) {
        shortLabel = this.PREFIXES[prefix].short + shortLabel;
      }
      return shortLabel;
    },

    __getLongLabel: function(xUnit, prefix) {
      const baseUnit = this.__getBaseUnit(xUnit);
      let longLabel = baseUnit ? baseUnit.long : xUnit;
      if (prefix && prefix in this.PREFIXES) {
        longLabel = this.PREFIXES[prefix].long + longLabel;
      }
      return longLabel;
    },

    getNextPrefix: function(prefix) {
      if ([null, undefined, ""].includes(prefix)) {
        prefix = "no-prefix";
      }
      const keys = Object.keys(this.PREFIXES);
      const idx = keys.indexOf(prefix);
      if (idx === -1) {
        return null;
      }
      if (idx === keys.length-1) {
        return this.PREFIXES[keys[0]];
      }
      return this.PREFIXES[keys[idx+1]];
    },

    getPrefixMultiplier: function(prefix) {
      if ([null, undefined, ""].includes(prefix)) {
        prefix = "no-prefix";
      }
      if (prefix in this.PREFIXES) {
        return this.PREFIXES[prefix].multiplier;
      }
      return 1;
    },

    composeXUnit: function(unit, unitPrefix) {
      if (unit === undefined) {
        return null;
      }
      let xUnit = "";
      if (unitPrefix) {
        xUnit += unitPrefix + "-";
      }
      xUnit += unit;
      return xUnit;
    },

    decomposeXUnit: function(xUnit) {
      const unitSplit = xUnit.split("-");
      let unitPrefix = null;
      let unit = null;
      if (unitSplit.length === 2) {
        unitPrefix = unitSplit[0];
        unit = unitSplit[1];
      } else {
        unit = unitSplit[0];
      }
      return {
        unitPrefix,
        unit
      };
    }
  }
});
