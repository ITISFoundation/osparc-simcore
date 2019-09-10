/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("qxapp.statics.NodeStatics", {
  statics: {
    CATEGORIES: {
      postpro: {
        label: "Postpro",
        icon: "@FontAwesome5Solid/chart-bar/"
      },
      notebook: {
        label: "Notebook",
        icon: "@FontAwesome5Solid/file-code/"
      },
      solver: {
        label: "Solver",
        icon: "@FontAwesome5Solid/calculator/"
      },
      simulator: {
        label: "Simulator",
        icon: "@FontAwesome5Solid/brain/"
      },
      modeling: {
        label: "Modeling",
        icon: "@FontAwesome5Solid/cube/"
      },
      data: {
        label: "Data",
        icon: "@FontAwesome5Solid/file/"
      }
    },
    TYPES: {
      computational: {
        label: "Computational",
        icon: "@FontAwesome5Solid/cogs/"
      },
      dynamic: {
        label: "Interactive",
        icon: "@FontAwesome5Solid/mouse-pointer/"
      },
      container: {
        label: "Group of nodes",
        icon: "@FontAwesome5Solid/box-open/"
      }
    },
    getCategory: function(category) {
      return this.self().CATEGORIES[category.trim().toLowerCase()];
    },
    getType: function(type) {
      return this.self().TYPES[type.trim().toLowerCase()];
    },

    __matchPortType: function(typeA, typeB) {
      if (typeA === typeB) {
        return true;
      }
      let mtA = qxapp.data.MimeType.getMimeType(typeA);
      let mtB = qxapp.data.MimeType.getMimeType(typeB);
      return mtA && mtB &&
        new qxapp.data.MimeType(mtA).match(new qxapp.data.MimeType(mtB));
    },

    areNodesCompatible: function(topLevelPort1, topLevelPort2) {
      console.log("areNodesCompatible", topLevelPort1, topLevelPort2);
      return topLevelPort1.isInput !== topLevelPort2.isInput;
    },

    arePortsCompatible: function(port1, port2) {
      return port1.type && port2.type && this.self().__matchPortType(port1.type, port2.type);
    },
  }
});
