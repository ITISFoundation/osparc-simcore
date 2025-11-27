/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.wrapper.BookACallIframe", {
  extend: qx.ui.embed.Iframe,

  construct: function() {
    this.base(arguments);

    this.setAppearance("iframe-no-border");

    this.initDevServiceUrl();

    // not only once, every time there is a load (e.g. when navigating in the iframe)
    this.addListener("load", () => this.__updateStyles(), this);
  },

  properties: {
    serviceUrl: {
      check: "String",
      nullable: true,
      init: null,
      apply: "__applyServiceUrl"
    }
  },

  statics: {
    NAME: "easy!appointments",
    VERSION: "1.5.2",
    URL: "https://easyappointments.org/",

    DEV_SERVICE_URL: "http://10.43.103.145/index.php",
  },

  members: {
    initDevServiceUrl: function() {
      this.setServiceUrl(this.self().DEV_SERVICE_URL);
    },

    __applyServiceUrl: function(url) {
      const params = [];
      const myAuthData = osparc.auth.Data.getInstance();
      const firstName = myAuthData.getFirstName();
      if (firstName) {
        params.push("first_name=" + encodeURIComponent(firstName));
      }
      const lastName = myAuthData.getLastName();
      if (lastName) {
        params.push("last_name=" + encodeURIComponent(lastName));
      }
      const email = myAuthData.getEmail();
      if (email) {
        params.push("email=" + encodeURIComponent(email));
      }

      if (params.length > 0) {
        url += "?" + params.join("&");
      }

      this.setSource(url);
    },

    __updateStyles: function() {
      const colorManager = qx.theme.manager.Color.getInstance();
      const iframe = this.getContentElement().getDomElement();
      const theme = {
        '--bs-body-bg': colorManager.resolve("background-main-1"),
        '--osparc-text-color': colorManager.resolve("text"),
        '--osparc-primary': colorManager.resolve("product-color"),
      };
      const url = new URL(this.getServiceUrl());
      iframe.contentWindow.postMessage({
        type: 'osparc-theme',
        theme
      }, url.origin); // targetOrigin = iframe origin
    },
  }
});
