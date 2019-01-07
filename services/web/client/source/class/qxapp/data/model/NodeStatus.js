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

qx.Class.define("qxapp.data.model.NodeStatus", {
  extend: qx.core.Object,

  construct: function() {
    this.base();
  },

  properties: {
    node: {
      check: "qxapp.data.model.Node",
      nullable: false
    }
  }
});
