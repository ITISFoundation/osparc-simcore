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

qx.Class.define("osparc.component.metadata.ServiceMetadataEditor", {
  extend: qx.ui.core.Widget,

  /**
    * @param serviceData {Object} Object containing the Service Data
    */
  construct: function(serviceData) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Grow());

    this.__serviceData = serviceData;

    this.__stack = new qx.ui.container.Stack();
    this.__displayView = this.__createDisplayView(serviceData);
    this.__stack.add(this.__displayView);
    this._add(this.__stack);
  },

  properties: {
    mode: {
      check: ["display", "edit"],
      init: "display",
      nullable: false,
      apply: "_applyMode"
    }
  },

  statics: {
    getMetadataTSR: function() {
      const metadataTSR = {
        "r01": {
          "title": "R1 - Define context clearly",
          "description": "Develop and document the subject, purpose, and intended \
                          use(s) of the model or simulation."
        },
        "r02": {
          "title": "R2 - Use appropiate data",
          "description": "Employ relevant and tracable inforamtion in the \
                          development or operation of a model or simulation."
        },
        "r03": {
          "title": "R3 - Evaluate within context",
          "description": "Verification, validation, uncertainty quantification, and \
                          sensitivity analysis of the model or simulation are \
                          accomplished with respect to the reality of interest and \
                          intended use(s) of the model or simulation."
        },
        "r04": {
          "title": "R4 - List limitations explicitly",
          "description": "Restrictions, constraints, or qualifications for or on the use of \
                          the model or simulation are available for consideration by the \
                          users or customers of a model or simulation."
        },
        "r05": {
          "title": "R5 - Use version control",
          "description": "Implement a system to trace the time history of M&S activities \
                          including delineation of contributors' efforts."
        },
        "r06": {
          "title": "R6 - Document adequately",
          "description": "Maintain up-to-date informative record of all M&S activities, \
                          including simulation code, model mark-up, scope and \
                          intended use of M&S activities, as well as users' and \
                          developers' guides."
        },
        "r07": {
          "title": "R7 - Disseminate broadly",
          "description": "Publish all components of M&S activities, including simulation \
                          software, models, simulation scenarios and results."
        },
        "r08": {
          "title": "R8 - Get independent reviews",
          "description": "Have the M&S activity reviewed by nonpartisan third-party \
                          users and developers."
        },
        "r09": {
          "title": "R9 - Test competing implementations",
          "description": "Use contrasting M&S execution strategies to check the \
                          conclusions of the different execution strategies against each \
                          other."
        },
        "r10": {
          "title": "R10 - Conform to standards",
          "description": "Adopt and promote generally applicable and discipline \
                          specific operating procedures, guidelines, and regulations \
                          accepted as best practices."
        }
      };
      return metadataTSR;
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
          "description": "Unlcear to the M&S practitioners familiar with the application \
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
          "outreach": "Outreach to application-domain experts who may not be m&S practitioners"
        }
      };
      return conformanceLevel;
    },

    getDummyMetadataTSR: function() {
      const maxLevel = 5; // random integer from 0-4
      const dummyMetadataTSR = {
        "r01": {
          "level": Math.floor(Math.random()*(maxLevel))
        },
        "r02": {
          "level": Math.floor(Math.random()*(maxLevel))
        },
        "r03": {
          "level": Math.floor(Math.random()*(maxLevel))
        },
        "r04": {
          "level": Math.floor(Math.random()*(maxLevel))
        },
        "r05": {
          "level": Math.floor(Math.random()*(maxLevel))
        },
        "r06": {
          "level": Math.floor(Math.random()*(maxLevel))
        },
        "r07": {
          "level": Math.floor(Math.random()*(maxLevel))
        },
        "r08": {
          "level": Math.floor(Math.random()*(maxLevel))
        },
        "r09": {
          "level": Math.floor(Math.random()*(maxLevel))
        },
        "r10": {
          "level": Math.floor(Math.random()*(maxLevel))
        }
      };
      return dummyMetadataTSR;
    }
  },

  members: {
    __serviceData: null,
    __stack: null,
    __displayView: null,
    __editView: null,

    __createDisplayView: function(serviceData) {
      const displayView = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
      console.log(serviceData);
      return displayView;
    },

    _applyMode: function(mode) {
      switch (mode) {
        case "display":
          this.__stack.setSelection([this.__displayView]);
          break;
      }
    },

    __isUserOwner: function() {
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      if (myGid && osparc.component.export.ServicePermissions.canGroupWrite(this.__serviceData["access_rights"], myGid)) {
        return true;
      }
      return false;
    }
  }
});
