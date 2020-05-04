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
    HEARTBEAT_EMIT_INTERVAL: 2 * 1000,  // in millisencond
  },

  construct: function() {
    this.__clientHeartbeatPinger = new qx.event.Timer(
      osparc.io.WatchDog.HEARTBEAT_EMIT_INTERVAL
    );
    this.__clientHeartbeatPinger.addListener("interval", function() {
      const socket = osparc.wrapper.WebSocket.getInstance();
      try{
        socket.emit("client_heartbeat");
      }catch(error) {
        // no need to handle the error, nor does it need to cause further issues
        // it is ok to eat it up
      }
    }, this);
  },

  properties: {
    onLine: {
      check: "Boolean",
      init: false,
      nullable: false,
      apply: "_applyOnLine"
    }
  },

  members: {
    _applyOnLine: function(value) {
      let logo = osparc.component.widget.LogoOnOff.getInstance();
      if (logo) {
        logo.setOnLine(value);
      }
      value ? this.__clientHeartbeatPinger.start() : this.__clientHeartbeatPinger.stop();
    }
  } // members
});
