/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Class that stores Edge data.
 *
 *                                    -> {EDGES}
 * STUDY -> METADATA + WORKBENCH ->|
 *                                    -> {LINKS}
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let edge = new osparc.data.model.Edge(edgeId, node1, node2);
 * </pre>
 */

qx.Class.define("osparc.data.model.Edge", {
  extend: qx.core.Object,

  /**
    * @param edgeId {String} uuid if the edge. If not provided, a random one will be assigned
    * @param nodeFrom {osparc.data.model.Node | Object} node/parameter where the edge comes from
    * @param nodeTo {osparc.data.model.Node} node where the edge goes to
    * @param bothNodes {boolean?} parameter where the edge comes from
    */
  construct: function(edgeId, nodeFrom, nodeTo, bothNodes = true) {
    this.base();

    this.setEdgeId(edgeId || osparc.utils.Utils.uuidv4());
    bothNodes ? this.setInputNode(nodeFrom) : this.setInputParameter(nodeFrom);
    this.setOutputNode(nodeTo);
  },

  properties: {
    edgeId: {
      check: "String",
      nullable: false
    },

    inputNode: {
      check: "osparc.data.model.Node",
      init: null,
      nullable: true
    },

    inputParameter: {
      check: "Object",
      init: null,
      nullable: true
    },

    outputNode: {
      check: "osparc.data.model.Node",
      apply: "__applyOutputNode",
      nullable: false
    },

    portConnected: {
      check: "Boolean",
      init: false,
      event: "changePortConnected",
      nullable: false
    }
  },

  statics: {
    checkAnyPortsConnected: function(node1, node2) {
      if (node2.getPropsForm()) {
        const links = node2.getPropsForm().getLinks();
        const anyConnected = links.some(link => link["nodeUuid"] === node1.getNodeId());
        return anyConnected;
      }
      return false;
    }
  },

  members: {
    getInputNodeId: function() {
      if (this.getInputNode()) {
        return this.getInputNode().getNodeId();
      }
      return null;
    },

    getInputParameterId: function() {
      if (this.getInputParameter()) {
        return this.getInputParameter()["id"];
      }
      return null;
    },

    getOutputNodeId: function() {
      return this.getOutputNode().getNodeId();
    },

    __applyOutputNode: function(node2) {
      node2.bind("portsConnected", this, "portConnected", {
        converter: () => {
          const isConnected = this.__checkIsPortConnected();
          return Boolean(isConnected);
        }
      });
    },

    __checkIsPortConnected: function() {
      let anyConnected = false;
      const node1 = this.getInputNode();
      let node2 = this.getOutputNode();
      if (node2.getPropsForm()) {
        anyConnected |= this.self().checkAnyPortsConnected(node1, node2);
      }
      if (node2.isContainer()) {
        const innerNodes = node2.getInnerNodes();
        for (const innerNodeId in innerNodes) {
          node2 = innerNodes[innerNodeId];
          if (node2.getPropsForm()) {
            anyConnected |= this.self().checkAnyPortsConnected(node1, node2);
          }
          break;
        }
      }
      return anyConnected;
    }
  }
});
