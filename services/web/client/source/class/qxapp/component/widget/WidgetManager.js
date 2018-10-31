qx.Class.define("qxapp.component.widget.WidgetManager", {
  extend: qx.core.Object,

  type: "singleton",

  members: {
    getWidgetForNode: function(nodeModel, projectId) {
      let nodeKey = nodeModel.getMetaData().key;
      if (nodeKey.includes("file-picker")) {
        let filePicker = new qxapp.component.widget.FilePicker(nodeModel, projectId);
        return filePicker;
      }
      return null;
    }
  }
});
