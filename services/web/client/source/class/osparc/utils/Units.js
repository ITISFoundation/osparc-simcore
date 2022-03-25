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

    __isUnitRegistered: function(unitKey) {
      return Boolean(unitKey in this.BASE_UNITS);
    },

    __getBaseUnit: function(unitKey) {
      return unitKey in this.BASE_UNITS ? this.BASE_UNITS[unitKey] : null;
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

    __getPrefixMultiplier: function(prefix) {
      if ([null, undefined, ""].includes(prefix)) {
        prefix = "no-prefix";
      }
      if (prefix in this.PREFIXES) {
        return this.PREFIXES[prefix].multiplier;
      }
      return 1;
    },

    getLabels: function(unit, prefix) {
      if (this.__isUnitRegistered(unit)) {
        return {
          unitShort: this.__getShortLabel(unit, prefix),
          unitLong: this.__getLongLabel(unit, prefix)
        };
      }
      return null;
    },

    // One up and one down, or all the way to the SI
    getNextPrefix: function(prefix, originalPrefix) {
      if ([null, undefined, ""].includes(prefix)) {
        prefix = "no-prefix";
      }
      if ([null, undefined, ""].includes(originalPrefix)) {
        originalPrefix = "no-prefix";
      }
      const keys = Object.keys(this.PREFIXES);
      const orignalIdx = keys.indexOf(originalPrefix);
      if (orignalIdx === -1) {
        return null;
      }
      const midPrefix = Math.min(keys.length-2, Math.max(orignalIdx, 1));
      const pKeys = Object.keys(this.PREFIXES).filter((_, idx) => Math.abs(midPrefix-idx) <=1);
      const idx = pKeys.indexOf(prefix);
      if (idx === pKeys.length-1) {
        return this.PREFIXES[pKeys[0]];
      }
      return this.PREFIXES[pKeys[idx+1]];
    },

    getMultiplier: function(oldPrefix, newPrefix) {
      const oldMulitplier = this.__getPrefixMultiplier(oldPrefix);
      const newMulitplier = this.__getPrefixMultiplier(newPrefix);
      const multiplier = oldMulitplier/newMulitplier;
      return multiplier;
    },

    convertValue: function(val, oldPrefix, newPrefix) {
      const multiplier = this.getMultiplier(oldPrefix, newPrefix);
      const newValue = val*multiplier;
      // strip extra zeros
      return parseFloat((newValue).toFixed(15));
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
