/* global qxapp */

qx.Class.define("qxapp.components.workbench.LinkBase", {
  extend: qx.core.Object,

  construct: function(representation) {
    this.base();

    this.setLinkId(qxapp.utils.Utils.uuidv4());

    this.setRepresentation(representation);
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
    outputNodeId: {
      init: null,
      check: "String"
    }
  }
});
