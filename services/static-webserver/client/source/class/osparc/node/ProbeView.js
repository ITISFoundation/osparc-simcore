/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.node.ProbeView", {
  extend: qx.ui.core.Widget,

  construct: function(node, portId) {
    this.base();

    this._setLayout(new qx.ui.layout.VBox());

    if (node) {
      this.setNode(node);
    }

    if (portId) {
      this.setPortId(portId);
    }
  },

  statics: {
    getOutputValues: function(metaStudy, nodeId, portId) {
      return new Promise((resolve, reject) => {
        metaStudy.getIterations()
          .then(iterations => {
            const outputValues = [];
            iterations.forEach(iteration => outputValues.push(osparc.data.model.Study.getOutputValue(iteration, nodeId, portId)));
            resolve(outputValues);
          })
          .catch(err => {
            reject(err);
          });
      });
    }
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
      init: null,
      nullable: false,
      apply: "__applyNode"
    },

    portId: {
      check: "String",
      init: null,
      nullable: false,
      apply: "__populateLayout"
    }
  },

  members: {
    __applyNode: function(node) {
      if (!node.isProbe()) {
        console.error("Only Probe nodes are supported");
      }
      this.__populateLayout();
    },

    __populateLayout: function() {
      const node = this.getNode();
      const portId = this.getPortId();
      if (!node) {
        return;
      }

      this._removeAll();
      const outputValues = this.self().getOutputValues(node.getStudy(), node, portId);
      outputValues.forEach(outputValue => {
        this._add(new qx.ui.basic.Label(outputValue));
      });
    }
  }
});
