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

qx.Class.define("osparc.node.slideshow.FilePickerView", {
  extend: osparc.node.slideshow.BaseNodeView,

  events: {
    "itemSelected": "qx.event.type.Event"
  },

  members: {
    // overridden
    _addSettings: function() {
      return;
    },

    // overridden
    _addIFrame: function() {
      this.__buildMyLayout();
    },

    // overridden
    _applyNode: function(node) {
      if (!node.isFilePicker()) {
        console.error("Only file picker nodes are supported");
      }
      this.base(arguments, node);
    },

    __buildMyLayout: function() {
      const node = this.getNode();
      if (!node) {
        return;
      }

      const filePicker = new osparc.file.FilePicker(node, "app");
      filePicker.addListener("itemSelected", () => {
        this.fireEvent("itemSelected");
        // eslint-disable-next-line no-underscore-dangle
        filePicker.__buildLayout();
      });
      [
        "itemReset",
        "fileUploaded"
      // eslint-disable-next-line no-underscore-dangle
      ].forEach(ev => filePicker.addListener(ev, () => filePicker.__buildLayout()));

      this._mainView.add(filePicker, {
        flex: 1
      });
    }
  }
});
