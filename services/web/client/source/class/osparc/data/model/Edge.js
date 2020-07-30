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
    * @param node1 {osparc.data.model.Node} node where the edge comes from
    * @param node2 {osparc.data.model.Node} node where the edge goes to
  */
  construct: function(edgeId, node1, node2) {
    this.base();

    this.setEdgeId(edgeId || osparc.utils.Utils.uuidv4());
    this.setInputNode(node1);
    this.setOutputNode(node2);
  },

  properties: {
    edgeId: {
      check: "String",
      nullable: false
    },

    inputNode: {
      check: "osparc.data.model.Node",
      nullable: false
    },

    outputNode: {
      check: "osparc.data.model.Node",
      nullable: false
    },

    isPortConnected: {
      check: "Boolean",
      init: false,
      nullable: false
    }
  },

  memebers: {
    getInputNodeId: function() {
      this.getInputNode().getNodeId();
    },

    getOutputNodeId: function() {
      this.getOutputNode().getNodeId();
    }
  }
});
