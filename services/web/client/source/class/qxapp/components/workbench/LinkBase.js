qx.Class.define("qxapp.components.workbench.LinkBase", {
  extend: qx.core.Object,

  construct: function(representation) {
    this.base();

    this.setRepresentation(representation);

    this.setLinkId(qxapp.utils.Utils.uuidv4());
  },

  properties: {
    representation: {
      init: null
    },
    linkId: {
      check: "String",
      nullable: false
    },
    inputNodeId: {
      init: null,
      check: "String"
    },
    inputPortId: {
      init: null,
      check: "String"
    },
    outputNodeId: {
      init: null,
      check: "String"
    },
    outputPortId: {
      init: null,
      check: "String"
    }
  }
});
