// DiskUsageManager (singleton)
// construct() { listen to socket }
// subscribe(id, cb) { keeps a map of callbacks. one array of callbacks per id }
// socketHandler(updatedId) { search the map and call all corresponding callbacks }
/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Julian Querido (jsaq007)

************************************************************************ */

qx.Class.define("osparc.workbench.DiskUsageController", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.__prevDiskUsageStateList = [];
    this.base(arguments);

    this.__socket = osparc.wrapper.WebSocket.getInstance().getSocket();
    if (!this.__socket) {
      console.error("Invalid WebSocket object obtained from source");
    }
    this.__socket.on("serviceDiskUsage", data => {
      console.log("serviceDiskUsage", data["node_id"] === this.__node.getNodeId(), data["node_id"], this.__node.getNodeId());
      if (data["node_id"] && this.__callbacks[data["node_id"]]) {
        //  notify
        console.log("this", this)
        this.diskUsageToUI(data);
        this.__callbacks[data["node_id"]].forEach(cb => {
          cb(data);
        })
      }
    });
    this.__callbacks = {};
    console.log("Executed!!!!")
  },


  members: {
    __socket: null,
    __callbacks: null,
    __lowDiskThreshold: null,
    __prevDiskUsageStateList: null,
    __diskUsage: null,
    __node: null,

    subscribe: function(nodeId, callback, node) {
      this.__node = node;
      if (this.__callbacks[nodeId]) {
        console.log("new subscribe to node", node.getNodeId() === nodeId, node.getLabel(), this.__callbacks[nodeId]);
        this.__callbacks[nodeId].push(callback);
      } else {
        console.log("Listen to node", node.getNodeId() === nodeId, node.getLabel(), this.__callbacks[nodeId] = [callback]);
        this.__callbacks[nodeId] = [callback];
      }
    },

    unsubscribe: function(nodeId, callback, node) {
      console.log("unsubscribe to node", nodeId, node.getLabel());
      if (this.__callbacks[nodeId]) {
        this.__callbacks[nodeId] = this.__callbacks[nodeId].filter(cb => cb !== callback)
      }
    },

    getDiskUsage: function(freeSpace) {
      const lowDiskSpacePreferencesSettings = osparc.Preferences.getInstance();
      this.__lowDiskThreshold = lowDiskSpacePreferencesSettings.getLowDiskSpaceThreshold();
      const warningSize = osparc.utils.Utils.gBToBytes(this.__lowDiskThreshold); // 5 GB Default
      const criticalSize = osparc.utils.Utils.gBToBytes(0.01); // 0 GB
      let warningLevel = "NORMAL"
      if (freeSpace <= criticalSize) {
        warningLevel = "CRITICAL"
      } else if (freeSpace <= warningSize) {
        warningLevel = "WARNING"
      } else {
        warningLevel = "NORMAL"
      }
      return warningLevel
    },

    diskUsageToUI: function(data) {
      const id = data["node_id"];
      const diskUsage = data.usage["/"]
      function isMatchingNodeId({nodeId}) {
        return nodeId === id;
      }
      function shouldDisplayMessage(prevDiskUsageState, warningLevel) {
        return prevDiskUsageState && prevDiskUsageState.nodeId === id && prevDiskUsageState.state !== warningLevel
      }

      let prevDiskUsageState = this.__prevDiskUsageStateList.find(isMatchingNodeId);

      const warningLevel = this.getDiskUsage(diskUsage.free);
      if (prevDiskUsageState === undefined) {
        this.__prevDiskUsageStateList.push({
          nodeId: id,
          state: "NORMAL"
        })
      }
      const freeSpace = osparc.utils.Utils.bytesToSize(diskUsage.free);

      const nodeName = this.__node.getLabel();
      let message;

      const objIndex = this.__prevDiskUsageStateList.findIndex((obj => obj.nodeId === id));
      switch (warningLevel) {
        case "CRITICAL":
          if (shouldDisplayMessage(prevDiskUsageState, warningLevel)) {
            message = qx.locale.Manager.tr(`Out of Disk Space on "Service Filesystem" for ${nodeName}<br />The volume Service Filesystem has only ${freeSpace} disk space remaining. You can free up disk space by removing unused files in your service. Alternatively, you can run your service with a pricing plan that supports your storage requirements.`);
            osparc.FlashMessenger.getInstance().logAs(message, "ERROR");
            this.__prevDiskUsageStateList[objIndex].state = warningLevel;
          }
          break;
        case "WARNING":
          if (shouldDisplayMessage(prevDiskUsageState, warningLevel)) {
            message = qx.locale.Manager.tr(`Low Disk Space on "Service Filesystem" for ${nodeName}<br />The volume Service Filesystem has only ${freeSpace} disk space remaining. You can free up disk space by removing unused files in your service. Alternatively, you can run your service with a pricing plan that supports your storage requirements.`);
            osparc.FlashMessenger.getInstance().logAs(message, "WARNING");
            this.__prevDiskUsageStateList[objIndex].state = warningLevel;
          }
          break;
        default:
          this.__prevDiskUsageStateList[objIndex].state = "NORMAL";
          break;
      }
    },
  }
});
