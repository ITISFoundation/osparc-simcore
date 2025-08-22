/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * The locked page
 *
 * -----------------------
 * |                     |
 * |                     |
 * | oSparc/service logo |
 * |  reason why locked  |
 * |                     |
 * -----------------------
 *
 */
qx.Class.define("osparc.ui.message.NodeLockedPage", {
  extend: osparc.ui.message.Loading,

  properties: {
    node: {
      check: "osparc.data.model.Node",
      init: null,
      nullable: false,
      event: "changeNode",
      apply: "__applyNode"
    },
  },

  members: {
    __applyNode: function(node) {
      const thumbnail = node.getMetadata()["thumbnail"];
      if (thumbnail) {
        this.setLogo(thumbnail);
      }

      const lockState = node.getStatus().getLockState();

      const updateTitle = () => {
        if (lockState.isLocked()) {
          this._setHeaderIcon("@FontAwesome5Solid/lock/20");
          this._setHeaderTitle(this.tr("The application is being used"));
        } else {
          this._setHeaderIcon("@FontAwesome5Solid/lock-open/20");
          this._setHeaderTitle(this.tr("The application is not being used"));
        }
      };
      updateTitle();
      lockState.addListener("changeLocked", updateTitle);
    },
  }
});
