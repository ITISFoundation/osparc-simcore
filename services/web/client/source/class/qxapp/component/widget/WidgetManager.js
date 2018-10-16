qx.Class.define("qxapp.component.widget.WidgetManager", {
  extend: qx.core.Object,

  type: "singleton",

  members: {
    getWidgetForNode: function(node) {
      let nodeKey = node.getMetaData().key;
      if (nodeKey.includes("file-picker")) {
        let filePicker = new qxapp.component.widget.FilePicker(node);
        return filePicker;
      }
      return null;
    }
  }
});
