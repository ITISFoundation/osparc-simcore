qx.Class.define("qxapp.components.widgets.WidgetManager", {
  extend: qx.core.Object,

  type: "singleton",

  members: {
    getWidgetForNode: function(node) {
      let nodeKey = node.getMetaData().key;
      if (nodeKey.includes("FilePicker")) {
        let filePicker = new qxapp.components.widgets.FilePicker(node);
        return filePicker;
      } else if (nodeKey.includes("s4l/Simulator/LF/")) {
        let simulatorSetting = new qxapp.components.widgets.SimulatorSetting();
        simulatorSetting.setNode(node);
        return simulatorSetting;
      } else if (nodeKey.includes("s4l/Simulator/")) {
        let simulator = new qxapp.components.widgets.Simulator(node);
        return simulator;
      }
      return null;
    }
  }
});
