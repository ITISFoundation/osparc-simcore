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
  * @asset(pacemaker.js)
  * @ignore(Worker)
  */

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
  type: "singleton",

  construct: function() {
    this.__clientHeartbeatWWPinger = new Worker("resource/osparc/pacemaker.js");
    this.__clientHeartbeatWWPinger.onmessage = () => {
      this.__pingServer();
    };

    // register for socket.io event to change the default heartbeat interval
    const socket = osparc.wrapper.WebSocket.getInstance();
    const socketIoEventName = "set_heartbeat_emit_interval";
    socket.removeSlot(socketIoEventName);
    socket.on(socketIoEventName, jsonString => {
      const data = JSON.parse(jsonString);
      const newInterval = parseInt(data.interval) * 1000;
      this.setHeartbeatInterval(newInterval);
    }, this);
  },

  properties: {
    online: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeOnline",
      apply: "_applyOnline"
    },

    heartbeatInterval: {
      check: "Number",
      init: 2 * 1000, // in milliseconds
      nullable: false,
      apply: "_applyHeartbeatInterval"
    }
  },

  members: {
    __clientHeartbeatWWPinger: null,

    _applyOnline: function(value) {
      let logo = osparc.component.widget.LogoOnOff.getInstance();
      if (logo) {
        logo.setOnline(value);
      }

      if (value) {
        this.__clientHeartbeatWWPinger.postMessage(["start", this.getHeartbeatInterval()]);
      } else {
        this.__clientHeartbeatWWPinger.postMessage(["stop"]);
      }
    },

    _applyHeartbeatInterval: function(value) {
      this.__clientHeartbeatWWPinger.postMessage(["start", value]);
    },

    __pingServer: function() {
      const socket = osparc.wrapper.WebSocket.getInstance();
      try {
        socket.emit("client_heartbeat");
      } catch (error) {
        // no need to handle the error, nor does it need to cause further issues
        // it is ok to eat it up
      }
    }
  }
});
