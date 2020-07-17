/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Class that stores Node's Status.
 */

qx.Class.define("osparc.data.model.NodeStatus", {
  extend: qx.core.Object,

  construct: function() {
    this.base(arguments);
  },

  properties: {
    progress: {
      check: "Number",
      init: 0,
      event: "changeProgress"
    },

    interactiveStatus: {
      check: "String",
      nullable: true,
      event: "changeInteractiveStatus"
    }
  }
});
