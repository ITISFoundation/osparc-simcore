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

    const grid = new qx.ui.layout.Grid(5, 10);
    grid.setColumnFlex(0, 1);
    this._setLayout(grid);

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
        case "cookie-text": {
          const color = qx.theme.manager.Color.getInstance().resolve("text");
          const textLink = `<a href=https://itis.swiss/meta-navigation/privacy-policy/ style='color: ${color}' target='_blank'>Privacy Policy.</a>`;
          const text = this.tr("This website applies cookies to personalize your experience and to make our site easier to navigate. By visiting the site, you agree to the ") + textLink;
          control = new qx.ui.basic.Label(text).set({
            rich : true
          });
          this._add(control, {
            column: 0,
            row: 0
          });
          break;
        }
        case "accept-cookie":
          control = new qx.ui.form.CheckBox().set({
            value: true
          });
          this._add(control, {
            column: 1,
            row: 0
          });
          break;
        case "license-text": {
          const text = this.tr("It also uses third party software and libraries. By visiting the site, you agree to the ");
          control = new qx.ui.basic.Label(text).set({
            rich : true
          });
          osparc.store.Support.getLicenseURL()
            .then(licenseLink => {
              const lbl = control.getLabel();
              if (licenseLink) {
                const color = qx.theme.manager.Color.getInstance().resolve("text");
                const textLink = `<a href=${licenseLink} style='color: ${color}' target='_blank'>Licensing.</a>`;
                control.setLabel(lbl + textLink);
              } else {
                control.setLabel(lbl + this.tr("Licensing."));
              }
            });
          this._add(control, {
            column: 0,
            row: 1
          });
          break;
        }
        case "accept-license":
          control = new qx.ui.form.CheckBox().set({
            value: true
          });
          this._add(control, {
            column: 1,
            row: 1
          });
          break;
        case "control-buttons": {
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
            alignX: "right"
          })).set({
            padding: 2
          });
          this._add(control, {
            column: 0,
            row: 2,
            colSpan: 2
          });
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
      const checkButtons = [];
      this.getChildControl("cookie-text");
      const acceptCookie = this.getChildControl("accept-cookie");
      checkButtons.push(acceptCookie);

      if (osparc.utils.Utils.isProduct("tis") || osparc.utils.Utils.isProduct("s4llite")) {
        this.getChildControl("license-text");
        const acceptLicense = this.getChildControl("accept-license");
        checkButtons.push(acceptLicense);
      }

      const acceptBtn = this.getChildControl("accept-button");
      const evalAcceptButton = () => {
        acceptBtn.setEnabled(checkButtons.every(checkButton => checkButton.getValue()));
      };
      checkButtons.forEach(checkButton => checkButton.addListener("changeValue", () => evalAcceptButton()));
      acceptBtn.addListener("execute", () => this.fireEvent("cookiesAccepted"), this);
      evalAcceptButton();
    }
  }
});
