/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.ui.tree.ClassifiersTreeItem", {
  extend: qx.ui.tree.VirtualTreeItem,
  include: osparc.ui.tree.MHintInTree,

  members: {
    _addWidgets: function() {
      this.addSpacer();
      this.addOpenButton();
      this.addLabel();
      this._add(new qx.ui.core.Spacer(), {
        flex: 1
      });
    }
  }
});
