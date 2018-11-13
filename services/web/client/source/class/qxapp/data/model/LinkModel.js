qx.Class.define("qxapp.data.model.LinkModel", {
  extend: qx.core.Object,

  construct: function(linkId, node1Id, node2Id) {
    this.base();

    this.setLinkId(linkId || qxapp.utils.Utils.uuidv4());
    this.setInputNodeId(node1Id);
    this.setOutputNodeId(node2Id);
  },

  properties: {
    linkId: {
      check: "String",
      nullable: false
    },

    inputNodeId: {
      init: null,
      check: "String"
    },

    outputNodeId: {
      init: null,
      check: "String"
    }
  }
});
