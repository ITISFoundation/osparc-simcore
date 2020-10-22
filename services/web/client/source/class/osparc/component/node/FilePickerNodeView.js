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
  extend: osparc.component.node.BaseNodeView,

  /**
    * @param node {osparc.data.model.Node} Node owning the widget
    */
  construct: function(node) {
    this.base(arguments);

    this.set({
      node
    });
  },

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
      return;
    },

    __buildMyLayout: function() {
      const filePicker = this.__filePicker = new osparc.file.FilePicker(this.getNode());
      filePicker.buildLayout();
      filePicker.init();

      this._mainView.add(filePicker, {
        flex: 1
      });
    }
  }
});
