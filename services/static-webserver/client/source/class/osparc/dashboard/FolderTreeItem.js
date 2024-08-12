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

qx.Class.define("osparc.dashboard.FolderTreeItem", {
  extend: qx.ui.tree.VirtualTreeItem,

  members: {
    // overridden
    _addWidgets: function() {
      this.addIcon();
      this.addLabel();

      this.addWidget(new qx.ui.core.Spacer(), {
        flex: 1
      });
    }
  }
});
