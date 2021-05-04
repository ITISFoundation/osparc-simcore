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
  *
  */

qx.Class.define("osparc.component.node.FilePickerNodeView", {
  extend: osparc.component.node.NodeView,

  members: {
    __filePicker: null,

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
      if (!node.isFilePicker() && !node.isMultiFilePicker()) {
        console.error("Only file picker nodes are supported");
      }
      this.base(arguments, node);
    },

    __buildMyLayout: function() {
      const node = this.getNode();
      if (!node) {
        return;
      }

      const filePicker = this.__filePicker = new osparc.file.FilePicker(node);
      filePicker.buildLayout();
      filePicker.init();

      this._mainView.add(filePicker, {
        flex: 1
      });
    }
  }
});
