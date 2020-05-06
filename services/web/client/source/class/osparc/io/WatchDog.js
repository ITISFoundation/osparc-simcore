/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Singleton class that does some network connection checks.
 *
 * It has two levels:
 * - Listens to the online/offline event to check whether there is Internet connection or not.
 * - Checks whether the webserver is reachable by doing some HealthCheck calls.
 *
 * *Example*
 *
 * Here is a little example of how to use the class.
 *
 * <pre class='javascript'>
 *   osparc.io.WatchDog.getInstance().startCheck();
 * </pre>
 */

qx.Class.define("osparc.io.WatchDog", {
  extend: qx.core.Object,

  type : "singleton",

  statics : {
    DEFAULT_HEARTBEAT_EMIT_INTERVAL_MS: 2 * 1000 // in milliseconds
  },

  construct: function() {
    this.heartbeatInterval = osparc.io.WatchDog.DEFAULT_HEARTBEAT_EMIT_INTERVAL_MS;
    this.__clientHeartbeatPinger = new qx.event.Timer(this.heartbeatInterval);

    this.__clientHeartbeatPinger.addListener("interval", function() {
      const socket = osparc.wrapper.WebSocket.getInstance();
      try {
        socket.emit("client_heartbeat");
      } catch (error) {
        // no need to handle the error, nor does it need to cause further issues
        // it is ok to eat it up
      }
    }, this);

    // register for socket.io event to change the default heartbeat interval
    const socket = osparc.wrapper.WebSocket.getInstance();
    const socketIoEventName = "set_heartbeat_emit_interval";
    socket.removeSlot(socketIoEventName);
    socket.on(socketIoEventName, function(emitIntervalSeconds) {
      this.setHeartbeatInterval(parseInt(emitIntervalSeconds) * 1000);
    }, this);
  },

  properties: {
    onLine: {
      check: "Boolean",
      init: false,
      nullable: false,
      apply: "_applyOnLine"
    },
    heartbeatInterval: {
      init: 0,
      nullable: false,
      apply: "_applyHeartbeatInterval"
    }
  },

  members: {
    _applyOnLine: function(value) {
      let logo = osparc.component.widget.LogoOnOff.getInstance();
      if (logo) {
        logo.setOnLine(value);
      }
      value ? this.__clientHeartbeatPinger.start() : this.__clientHeartbeatPinger.stop();
    },
    _applyHeartbeatInterval: function(value) {
      this.__clientHeartbeatPinger.setInterval(value);
    }
  } // members
});
