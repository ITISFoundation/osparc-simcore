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

/**
  *
  */

qx.Class.define("osparc.component.node.DataSourceNodeView", {
  extend: osparc.component.node.BaseNodeView,

  members: {
    __filePicker: null,

    // overridden
    isSettingsGroupShowable: function() {
      return false;
    },

    // overridden
    _addSettings: function() {
      return;
    },

    // overridden
    _addIFrame: function() {
      this.__buildMyLayout();
    },

    // overridden
    _openEditAccessLevel: function() {
      return;
    },

    // overridden
    _applyNode: function(node) {
      if (!node.isDataSource()) {
        console.error("Only file picker nodes are supported");
      }
      this.base(arguments, node);
    },

    __buildMyLayout: function() {
      const node = this.getNode();
      if (!node) {
        return;
      }

      const label = new qx.ui.basic.Label("Hey");

      this._mainView.add(label, {
        flex: 1
      });
    }
  }
});
