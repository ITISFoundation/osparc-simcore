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
    _addWidgets: function() {
      this.addSpacer();
      // this.addOpenButton();
      const openButton = this.getChildControl("open");
      openButton.addListener("changeOpen", () => {
        console.log("changeOpen", this);
      }, this);
      openButton.addListener("changeVisibility", e => {
        // console.log("changeVisibility", this.getLabel() + e.getData(), this);
        openButton.show();
      }, this);
      this._add(openButton);
      this.addIcon();
      const label = this.getChildControl("label");
      this._add(label, {
        flex: 1
      });
    }
  }
});
