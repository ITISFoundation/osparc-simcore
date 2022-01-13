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

qx.Class.define("osparc.data.model.Slideshow", {
  extend: qx.core.Object,

  /**
   * @param slideshowData {Object} Object containing the serialized Slide Show Data
   */
  construct: function(slideshowData) {
    this.base(arguments);

    this.setData(slideshowData);
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
    getSortedNodes: function(slideshow) {
      const nodes = [];
      for (let nodeId in slideshow) {
        const node = slideshow[nodeId];
        nodes.push({
          ...node,
          nodeId
        });
      }
      nodes.sort((a, b) => (a.position > b.position) ? 1 : -1);
      return nodes;
    },

    getSortedNodeIds: function(slideshow) {
      const nodes = this.self().getSortedNodes(slideshow);
      const nodeIds = [];
      nodes.forEach(node => {
        nodeIds.push(node.nodeId);
      });
      return nodeIds;
    }
  },

  members: {
    isEmpty: function() {
      return !Object.keys(this.getData()).length;
    },

    getSortedNodes: function() {
      return this.self().getSortedNodes(this.getData());
    },

    getSortedNodeIds: function() {
      return this.self().getSortedNodeIds(this.getData());
    },

    insertNode: function(nodeId, pos) {
      const slideshow = this.getData();
      for (let nodeId2 in slideshow) {
        if (slideshow[nodeId2].position >= pos) {
          slideshow[nodeId2].position++;
        }
      }
      slideshow[nodeId] = {
        position: pos
      };
    },

    removeNode: function(nodeId) {
      const slideshow = this.getData();
      if (nodeId in slideshow) {
        const pos = slideshow[nodeId];
        for (let nodeId2 in slideshow) {
          if (slideshow[nodeId2].position > pos.position) {
            slideshow[nodeId2].position--;
          }
        }

        delete slideshow[nodeId];
      }
    },

    getPosition: function(nodeId) {
      const slideshow = this.getData();
      if (nodeId in slideshow) {
        return slideshow[nodeId].position;
      }
      return -1;
    },

    addNodeToSlideshow: function(newNode, leftNodeId, rightNodeId) {
      const nodeId = newNode.getNodeId();
      if (leftNodeId) {
        let leftPos = this.getPosition(leftNodeId);
        this.insertNode(nodeId, leftPos+1);
      } else if (rightNodeId) {
        const rightPos = this.getPosition(rightNodeId);
        this.insertNode(nodeId, rightPos);
      } else {
        this.insertNode(nodeId, 0);
      }
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
