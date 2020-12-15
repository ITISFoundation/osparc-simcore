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

qx.Class.define("osparc.component.metadata.ServiceQuality", {
  type: "static",

  statics: {
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
      const conformanceLevels = osparc.component.metadata.ServiceQuality.getConformanceLevel();
      Object.values(conformanceLevels).forEach(conformanceLevel => {
        if (conformanceLevel.level === level) {
          confLevel = conformanceLevel;
        }
      });
      return confLevel;
    },

    getDefaultQuality: function() {
      const defaultQuality = {};
      defaultQuality["annotations"] = osparc.component.metadata.ServiceQuality.getDefaultQualityAnnotations();
      defaultQuality["tsr"] = osparc.component.metadata.ServiceQuality.getDefaultQualityTSR();
      return defaultQuality;
    },

    getDefaultQualityAnnotations: function() {
      const defaultAnnotations = {
        "certificationStatus": "Uncertified",
        "certificationLink": "",
        "purpose": "",
        "vandv": "",
        "limitations": "",
        "documentation": "",
        "standards": ""
      };
      return defaultAnnotations;
    },

    getDefaultQualityTSR: function() {
      const defaultTSR = {
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
        "r08": {
          "level": 0,
          "references": ""
        },
        "r09": {
          "level": 0,
          "references": ""
        },
        "r10": {
          "level": 0,
          "references": ""
        }
      };
      return defaultTSR;
    },

    computeTSRScore: function(metadataTSR) {
      let score = 0;
      let maxScore = 0;
      Object.values(metadataTSR).forEach(rule => {
        score += rule.level;
        maxScore += 4;
      });
      return {
        score,
        maxScore
      };
    }
  }
});
