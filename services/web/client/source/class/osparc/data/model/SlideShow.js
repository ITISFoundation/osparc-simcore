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

  events: {
    "changeSlideshow": "qx.event.type.Event"
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

    insertNode: function(nodeId, pos) {
      const slideShow = this.getData();
      for (let nodeId2 in slideShow) {
        if (slideShow[nodeId2].position >= pos) {
          slideShow[nodeId2].position++;
        }
      }
      slideShow[nodeId] = {
        position: pos
      };
    },

    removeNode: function(nodeId) {
      const slideShow = this.getData();
      if (nodeId in slideShow) {
        const pos = slideShow[nodeId];
        for (let nodeId2 in slideShow) {
          if (slideShow[nodeId2].position >= pos) {
            slideShow[nodeId2].position--;
          }
        }

        delete slideShow[nodeId];
      }
    },

    getPosition: function(nodeId) {
      const slideShow = this.getData();
      if (nodeId in slideShow) {
        return slideShow[nodeId].position;
      }
      return -1;
    },

    __moveNode: function(nodes, from, to) {
      let numberOfDeletedElm = 1;
      const elm = nodes.splice(from, numberOfDeletedElm)[0];
      numberOfDeletedElm = 0;
      nodes.splice(to, numberOfDeletedElm, elm);
    },

    serialize: function() {
      return this.getData();
    }
  }
});
