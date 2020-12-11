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

qx.Class.define("osparc.component.metadata.ServiceMetadata", {
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
      const conformanceLevels = osparc.component.metadata.ServiceMetadata.getConformanceLevel();
      Object.values(conformanceLevels).forEach(conformanceLevel => {
        if (conformanceLevel.level === level) {
          confLevel = conformanceLevel;
        }
      });
      return confLevel;
    },

    getDummyMetadata: function() {
      const dummyMetadata = osparc.component.metadata.ServiceMetadata.getDummyMetadataAnnotations();
      dummyMetadata["tsr"] = osparc.component.metadata.ServiceMetadata.getDummyMetadataTSR();
      return dummyMetadata;
    },

    getDummyMetadataAnnotations: function() {
      const dummyMetadataAnnotations = {
        "certificationStatus": "Uncertified",
        "certificationLink": "",
        "purpose": "",
        "vandv": "",
        "limitations": "",
        "documentation": "",
        "standards": ""
      };
      return dummyMetadataAnnotations;
    },

    getDummyMetadataTSR: function() {
      const maxLevel = 5; // random integer from 0-4
      const dummyMetadataTSR = {
        "r01": {
          "level": Math.floor(Math.random()*(maxLevel)),
          "references": "[osparc](https://osparc.io/)"
        },
        "r02": {
          "level": Math.floor(Math.random()*(maxLevel)),
          "references": ""
        },
        "r03": {
          "level": Math.floor(Math.random()*(maxLevel)),
          "references": ""
        },
        "r04": {
          "level": Math.floor(Math.random()*(maxLevel)),
          "references": "[Ten Simple Rules](https://www.imagwiki.nibib.nih.gov/content/10-simple-rules-conformance-rubric)"
        },
        "r05": {
          "level": Math.floor(Math.random()*(maxLevel)),
          "references": ""
        },
        "r06": {
          "level": Math.floor(Math.random()*(maxLevel)),
          "references": ""
        },
        "r07": {
          "level": Math.floor(Math.random()*(maxLevel)),
          "references": ""
        },
        "r08": {
          "level": Math.floor(Math.random()*(maxLevel)),
          "references": ""
        },
        "r09": {
          "level": Math.floor(Math.random()*(maxLevel)),
          "references": ""
        },
        "r10": {
          "level": Math.floor(Math.random()*(maxLevel)),
          "references": ""
        }
      };
      return dummyMetadataTSR;
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
