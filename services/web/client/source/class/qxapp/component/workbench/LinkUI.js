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

qx.Class.define("qxapp.component.workbench.LinkUI", {
  extend: qx.core.Object,

  construct: function(link, representation) {
    this.base();

    this.setLink(link);
    this.setRepresentation(representation);
  },

  events: {
    "linkSelected": "qx.event.type.Data"
  },

  properties: {
    link: {
      check: "qxapp.data.model.Link",
      nullable: false
    },

    representation: {
      init: null
    }
  },

  members: {
    getLinkId: function() {
      return this.getLink().getLinkId();
    }
  }
});
