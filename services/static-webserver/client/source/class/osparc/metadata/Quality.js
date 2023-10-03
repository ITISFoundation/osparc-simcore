/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.metadata.Quality", {
  type: "static",

  statics: {
    attachQualityToObject: function(obj) {
      if (!("quality" in obj)) {
        obj["quality"] = {};
      }
      if (!("enabled" in obj["quality"])) {
        obj["quality"]["enabled"] = true;
      }

      if ("tsr" in obj["quality"]) {
        obj["quality"]["tsr_current"] = obj["quality"]["tsr"];
        delete obj["quality"]["tsr"];
      }

      const defaultCurrentTSR = osparc.metadata.Quality.getDefaultCurrentQualityTSR();
      if (!("tsr_current" in obj["quality"])) {
        obj["quality"]["tsr_current"] = defaultCurrentTSR;
      }
      Object.keys(defaultCurrentTSR).forEach(sectionKey => {
        if (!(sectionKey in obj["quality"]["tsr_current"])) {
          obj["quality"]["tsr_current"][sectionKey] = defaultCurrentTSR[sectionKey];
        }
      });

      const defaultTargetTSR = osparc.metadata.Quality.getDefaultTargetQualityTSR();
      if (!("tsr_target" in obj["quality"])) {
        obj["quality"]["tsr_target"] = defaultTargetTSR;
      }
      Object.keys(defaultTargetTSR).forEach(sectionKey => {
        if (!(sectionKey in obj["quality"]["tsr_target"])) {
          obj["quality"]["tsr_target"][sectionKey] = defaultTargetTSR[sectionKey];
        }
      });

      if (("annotations" in obj["quality"])) {
        delete obj["quality"]["annotations"];
      }
    },

    isEnabled: function(quality) {
      return quality && "enabled" in quality && quality["enabled"];
    },

    getConformanceLevel: function() {
      const conformanceLevel = {
        "l00": {
          "title": "Insufficient",
          "description": "Missing or grossly incomplete information to properly evaluate \
the conformance with the rule",
          "level": 0,
          "outreach": "None or very limited"
        },
        "l01": {
          "title": "Partial",
          "description": "Unclear to the M&S practitioners familiar with the application \
domain and the intended context of use",
          "level": 1,
          "outreach": "Outreach to application-domain specific M&S practitioners"
        },
        "l02": {
          "title": "Adequate",
          "description": "Can be understood by M&S practitioners familiar with the application \
domain and the intended context of use",
          "level": 2,
          "outreach": "Outreach to application-domain specific M&S practitioners"
        },
        "l03": {
          "title": "Extensive",
          "description": "Can be understood by M&S practitioners not familiar with the application \
domain and the intended context of use",
          "level": 3,
          "outreach": "Outreach to practitioners who may not be application-domain experts"
        },
        "l04": {
          "title": "Comprehensive",
          "description": "Can be understood by non-M&S practitioners familiar with the application \
domain and the intended context of use",
          "level": 4,
          "outreach": "Outreach to application-domain experts who may not be M&S practitioners"
        }
      };
      return conformanceLevel;
    },

    findConformanceLevel: function(level) {
      let confLevel = null;
      const conformanceLevels = osparc.metadata.Quality.getConformanceLevel();
      Object.values(conformanceLevels).forEach(conformanceLevel => {
        if (conformanceLevel.level === level) {
          confLevel = conformanceLevel;
        }
      });
      return confLevel;
    },

    getDefaultCurrentQualityTSR: function() {
      const defaultCurrentTSR = {
        "r01": {
          "level": 0,
          "references": ""
        },
        "r02": {
          "level": 0,
          "references": ""
        },
        "r03": {
          "level": 0,
          "references": ""
        },
        "r03b": {
          "references": ""
        },
        "r03c": {
          "references": ""
        },
        "r04": {
          "level": 0,
          "references": ""
        },
        "r05": {
          "level": 0,
          "references": ""
        },
        "r06": {
          "level": 0,
          "references": ""
        },
        "r07": {
          "level": 0,
          "references": ""
        },
        "r07b": {
          "references": ""
        },
        "r07c": {
          "references": ""
        },
        "r07d": {
          "references": ""
        },
        "r07e": {
          "references": ""
        },
        "r08": {
          "level": 0,
          "references": ""
        },
        "r08b": {
          "references": ""
        },
        "r09": {
          "level": 0,
          "references": ""
        },
        "r10": {
          "level": 0,
          "references": ""
        },
        "r10b": {
          "references": ""
        }
      };
      return defaultCurrentTSR;
    },

    getDefaultTargetQualityTSR: function() {
      const defaultTargetTSR = {
        "r01": {
          "level": 4,
          "references": ""
        },
        "r02": {
          "level": 4,
          "references": ""
        },
        "r03": {
          "level": 4,
          "references": ""
        },
        "r03b": {
          "references": ""
        },
        "r03c": {
          "references": ""
        },
        "r04": {
          "level": 4,
          "references": ""
        },
        "r05": {
          "level": 4,
          "references": ""
        },
        "r06": {
          "level": 4,
          "references": ""
        },
        "r07": {
          "level": 4,
          "references": ""
        },
        "r07b": {
          "references": ""
        },
        "r07c": {
          "references": ""
        },
        "r07d": {
          "references": ""
        },
        "r07e": {
          "references": ""
        },
        "r08": {
          "level": 4,
          "references": ""
        },
        "r08b": {
          "references": ""
        },
        "r09": {
          "level": 4,
          "references": ""
        },
        "r10": {
          "level": 4,
          "references": ""
        },
        "r10b": {
          "references": ""
        }
      };
      return defaultTargetTSR;
    },

    computeTSRScore: function(currentTSR, targetTSR) {
      let score = 0;
      let targetScore = 0;
      let maxScore = 0;
      Object.entries(currentTSR).forEach(([tsrKey, cTSR]) => {
        if ("level" in cTSR && "level" in targetTSR[tsrKey]) {
          score += cTSR.level;
          targetScore += targetTSR[tsrKey].level;
          maxScore += 4;
        }
      });
      return {
        score,
        targetScore,
        maxScore
      };
    }
  }
});
