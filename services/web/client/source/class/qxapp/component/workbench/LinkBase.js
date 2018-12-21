/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("qxapp.component.workbench.LinkBase", {
  extend: qx.core.Object,

  construct: function(linkModel, representation) {
    this.base();

    this.setLinkModel(linkModel);
    this.setRepresentation(representation);
  },

  events: {
    "linkSelected": "qx.event.type.Data"
  },

  properties: {
    linkModel: {
      check: "qxapp.data.model.LinkModel",
      nullable: false
    },

    representation: {
      init: null
    }
  },

  members: {
    getLinkId: function() {
      return this.getLinkModel().getLinkId();
    }
  }
});
