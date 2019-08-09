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

  construct: function() {
    let resource = osparc.io.rest.ResourceFactory.getInstance().createHealthCheck();
    this.__healthCheckResource = resource.healthCheck;

    const interval = 5000;
    this.__timer = new qx.event.Timer(interval);

    window.addEventListener("online", this.__updateOnlineStatus, this);
    window.addEventListener("offline", this.__updateOnlineStatus, this);
  },

  properties: {
    onLine: {
      check: "Boolean",
      init: true,
      nullable: false
    },

    healthCheck: {
      check: "Boolean",
      init: true,
      nullable: false
    }
  },

  members: {
    __healthCheckResource: null,
    __timer: null,

    startCheck: function() {
      let timer = this.__timer;
      timer.addListener("interval", () => {
        if (this.getOnLine()) {
          this.__checkHealthCheckAsync();
        }
      }, this);
      timer.start();
      this.__checkHealthCheckAsync();
    },

    stopCheck: function() {
      if (this.__timer && this.__timer.isEnabled()) {
        this.__timer.stop();
      }
    },

    __checkHealthCheckAsync: function() {
      let resources = this.__healthCheckResource;
      resources.addListener("getSuccess", e => {
        this.__updateHealthCheckStatus(true);
      }, this);
      resources.addListener("getError", e => {
        this.__updateHealthCheckStatus(false);
      }, this);
      resources.get();
    },

    __updateOnlineStatus: function(e) {
      this.setOnLine(window.navigator.onLine);
      if (this.getOnLine()) {
        osparc.component.message.FlashMessenger.getInstance().info("Internet is back");
      } else {
        osparc.component.message.FlashMessenger.getInstance().error("Internet is down");
      }
    },

    __updateHealthCheckStatus: function(status) {
      this.setHealthCheck(status);
      let logo = osparc.component.widget.LogoOnOff.getInstance();
      if (logo) {
        logo.online(status);
      }
    }
  } // members
});
