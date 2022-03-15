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
    BASE_UNITS: [{
      meter: {
        quantity: "length",
        alias: ["meter", "m", "metre"],
        favAlias: "meter"
      },
      second: {
        quantity: "time",
        alias: ["second", "s", "sec"],
        favAlias: "second"
      },
      ampere : {
        quantity: "current",
        alias: ["ampere", "A", "amp"],
        favAlias: "ampere"
      },
      candela: {
        quantity: "luminosity",
        alias: ["candela", "cd", "candle"],
        favAlias: "candela"
      },
      gram: {
        quantity: "mass",
        alias: ["gram", "g"],
        favAlias: "gram"
      },
      mole: {
        quantity: "substance",
        alias: ["mole", "mol"],
        favAlias: "mole"
      },
      kelvin: {
        quantity: "temperature",
        alias: ["kelvin", "K", "degK", "°K", "degree_Kelvin", "degreeK"],
        favAlias: "kelvin"
      },
      radian: {
        quantity: "radian",
        alias: ["radian", "rad"],
        favAlias: "radian"
      },
      degree: {
        quantity: "angle",
        alias: ["degree", "deg"],
        favAlias: "degree"
      }
    }]
  }
});
