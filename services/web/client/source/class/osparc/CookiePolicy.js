/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * The Cookie Policy widget and utils
 *
 */
qx.Class.define("osparc.CookiePolicy", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.VBox());

    this.__buildLayout();
  },

  events: {
    "cookiesAccepted": "qx.event.type.Event",
    "cookiesDeclined": "qx.event.type.Event"
  },

  statics: {
    COOKIES_ACCEPTED_NAME: "cookies_v0:accepted",

    areCookiesAccepted: function() {
      const cookiesAccepted = osparc.utils.Utils.cookie.getCookie(this.COOKIES_ACCEPTED_NAME);
      return (cookiesAccepted === "true");
    },

    acceptCookies: function() {
      const expirationDays = 60;
      osparc.utils.Utils.cookie.setCookie(this.COOKIES_ACCEPTED_NAME, true, expirationDays);
    },

    declineCookies: function() {
      osparc.utils.Utils.cookie.deleteCookie(this.COOKIES_ACCEPTED_NAME);
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "text": {
          const text = this.tr("This website applies cookies to personalize your \
          experience and to make our site easier to navigate. By visiting \
          the site, you are agreeing to this use and to our \
          <a href=https://itis.swiss/meta-navigation/privacy-policy/ target='_blank'>Privacy Policy.</a>");
          control = new qx.ui.basic.Label(text).set({
            rich : true
          });
          this._add(control, {
            flex: 1
          });
          break;
        }
        case "control-buttons": {
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
            alignX: "right"
          })).set({
            padding: 2
          });
          this._add(control);
          break;
        }
        case "decline-button": {
          const ctrlBtns = this.getChildControl("control-buttons");
          control = new qx.ui.form.Button(this.tr("Decline")).set({
            visibility: "excluded",
            allowGrowX: false
          });
          osparc.utils.Utils.setIdToWidget(control, "declineCookiesBtn");
          ctrlBtns.add(control);
          break;
        }
        case "accept-button": {
          const ctrlBtns = this.getChildControl("control-buttons");
          control = new qx.ui.form.Button(this.tr("Accept")).set({
            allowGrowX: false
          });
          osparc.utils.Utils.setIdToWidget(control, "acceptCookiesBtn");
          ctrlBtns.add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("text");

      const declineBtn = this.getChildControl("decline-button");
      declineBtn.addListener("execute", () => {
        this.fireEvent("cookiesDeclined");
      }, this);

      const acceptBtn = this.getChildControl("accept-button");
      acceptBtn.addListener("execute", () => {
        this.fireEvent("cookiesAccepted");
      }, this);
    }
  }
});
