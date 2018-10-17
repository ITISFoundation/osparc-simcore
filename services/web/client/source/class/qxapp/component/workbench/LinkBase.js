qx.Class.define("qxapp.component.workbench.LinkBase", {
  extend: qx.core.Object,

  construct: function(representation) {
    this.base();

    this.setRepresentation(representation);

    this.setLinkId(qxapp.utils.Utils.uuidv4());
  },

  events: {
    "linkSelected": "qx.event.type.Data"
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
