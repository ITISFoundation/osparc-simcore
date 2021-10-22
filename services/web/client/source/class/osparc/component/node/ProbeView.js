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

qx.Class.define("osparc.component.node.ProbeView", {
  extend: osparc.component.node.BaseNodeView,

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

  members: {
    __probe: null,

    // overridden
    isSettingsGroupShowable: function() {
      return false;
    },

    // overridden
    _addSettings: function() {
      return;
    },

    // overridden
    _addIFrame: function() {
      this.__buildMyLayout();
    },

    // overridden
    _openEditAccessLevel: function() {
      return;
    },

    // overridden
    _applyNode: function(node) {
      if (!node.isProbe()) {
        console.error("Only Probe nodes are supported");
      }
      this.base(arguments, node);
    },

    __buildMyLayout: function() {
      const node = this.getNode();
      if (!node) {
        return;
      }
    }
  }
});
