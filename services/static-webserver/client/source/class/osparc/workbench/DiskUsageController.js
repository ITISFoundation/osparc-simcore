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
    this.base(arguments);

    this.__socket = osparc.wrapper.WebSocket.getInstance().getSocket();
    if (!this.__socket) {
      console.error("Invalid WebSocket object obtained from source");
    }
  },

  members: {
    __socket: null,

    subscribe: function(eventName, callback) {
      try {
        this.__socket.on(eventName, callback);
      } catch (error) {
        console.error("Error subscribing to event:", error);
      }
    },

    unsubscribe: function(eventName, callback) {
      try {
        this.__socket.off(eventName, callback);
      } catch (error) {
        console.error("Error unsubscribing from event:", error);
      }
    }
  }
});

qx.Class.define("osparc.workbench.DiskUsageListener", {
  extend: qx.core.Object,
  construct: function(manager) {
    this.base(arguments);
    this.__manager = manager;
  },

  members: {
    __manager: null,

    listen: function(eventName, callback) {
      this.__manager.subscribe(eventName, callback);
    }
  }
});
