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
    // Build base URL
    let url = osparc.wrapper.BookACallIframe.SERVICE_URL;

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

    // Call parent constructor
    this.base(arguments, url);

    this.addListener("load", () => this.__updateStyles(), this);
  },

  statics: {
    SERVICE_URL: "http://localhost:8000/booking",
  },

  members: {
    __updateStyles: function() {
      const colorManager = qx.theme.manager.Color.getInstance();
      const iframe = this.getContentElement().getDomElement();
      const theme = {
        '--bs-body-bg': colorManager.resolve("background-main-1"),
        '--osparc-primary': '"red"',
        '--osparc-secondary': '"green"',
        '--osparc-text': '"black"'
      };
      iframe.contentWindow.postMessage({
        type: 'osparc-theme',
        theme
      }, "http://localhost:8000"); // targetOrigin = iframe origin
    },
  }
});
