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
 *   osparc.WatchDog.getInstance().startCheck();
 * </pre>
 */

qx.Class.define("osparc.WatchDog", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.__clientHeartbeatWWPinger = new Worker("resource/osparc/pacemaker.js");
    this.__clientHeartbeatWWPinger.onmessage = () => {
      this.__pingServer();
    };

    // register for socket.io event to change the default heartbeat interval
    const socket = osparc.wrapper.WebSocket.getInstance();
    socket.bind("heartbeatInterval", this, "heartbeatInterval");
  },

  properties: {
    online: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeOnline",
      apply: "__applyOnline"
    },

    heartbeatInterval: {
      check: "Number",
      init: null,
      nullable: true,
      apply: "__applyHeartbeatInterval"
    },
  },

  members: {
    __clientHeartbeatWWPinger: null,

    __applyOnline: function(value) {
      const logo = osparc.navigation.LogoOnOff.getInstance();
      if (logo) {
        logo.setOnline(value);
      }

      value ? this.__startPinging() : this.__stopPinging();
    },

    __applyHeartbeatInterval: function(value) {
      if (value === null) {
        return;
      }

      this.__startPinging();
    },

    __startPinging: function() {
      const heartbeatInterval = this.getHeartbeatInterval() || 2000; // default to 2 seconds
      this.__clientHeartbeatWWPinger.postMessage(["start", heartbeatInterval]);
    },

    __stopPinging: function() {
      this.__clientHeartbeatWWPinger.postMessage(["stop"]);
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
