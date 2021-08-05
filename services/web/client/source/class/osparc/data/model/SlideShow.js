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

/**
 *
 */

qx.Class.define("osparc.data.model.SlideShow", {
  extend: qx.core.Object,

  /**
   * @param slideShowData {Object} Object containing the serialized Slide Show Data
   */
  construct: function(slideShowData) {
    this.base(arguments);

    this.setData(slideShowData);
  },

  properties: {
    data: {
      check: "Object",
      init: {},
      nullable: true
    }
  },

  statics: {
    getSortedNodes: function(slideShow) {
      const nodes = [];
      for (let nodeId in slideShow) {
        const node = slideShow[nodeId];
        nodes.push({
          ...node,
          nodeId
        });
      }
      nodes.sort((a, b) => (a.position > b.position) ? 1 : -1);
      return nodes;
    }
  },

  members: {
    isEmpty: function() {
      return !Object.keys(this.getData()).length;
    },

    getSortedNodes: function() {
      return this.self().getSortedNodes(this.getData());
    },

    removeNode: function(nodeId) {
      if (nodeId in this.getData()) {
        delete this.getData()[nodeId];
      }
    },

    getPosition: function(nodeId) {
      const slideShow = this.getData();
      if (nodeId in slideShow) {
        return slideShow[nodeId].position;
      }
      return -1;
    },

    serialize: function() {
      return this.getData();
    }
  }
});
