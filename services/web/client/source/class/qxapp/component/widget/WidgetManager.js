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
      /* else if (nodeKey.includes("s4l/Simulator/LF/")) {
        let simulatorSetting = new qxapp.component.widget.SimulatorSetting();
        simulatorSetting.setNode(node);
        return simulatorSetting;
      } else if (nodeKey.includes("s4l/Simulator/")) {
        let simulator = new qxapp.component.widget.Simulator(node);
        return simulator;
      }
      */
      return null;
    }
  }
});
