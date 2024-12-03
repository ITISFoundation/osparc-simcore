/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.dashboard.WorkspacesAndFoldersTreeItem", {
  extend: qx.ui.tree.VirtualTreeItem,

  construct: function() {
    this.base(arguments);

    this.set({
      indent: 12, // defaults to 19,
      decorator: "rounded",
      padding: 2,
      maxWidth: osparc.dashboard.ResourceBrowserBase.SIDE_SPACER_WIDTH - 12,
    });

    this.setNotHoveredStyle();
    this.__attachEventHandlers();
  },

  members: {
    __attachEventHandlers: function() {
      this.addListener("mouseover", () => {
        this.setHoveredStyle();
      });
      this.addListener("mouseout", () => {
        this.setNotHoveredStyle();
      });
    },

    setHoveredStyle: function() {
      osparc.utils.Utils.addBorder(this, 1, qx.theme.manager.Color.getInstance().resolve("text"));
    },

    setNotHoveredStyle: function() {
      osparc.utils.Utils.hideBorder(this);
    }
  },
});
