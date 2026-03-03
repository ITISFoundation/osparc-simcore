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
 * Cookie Policy footer banner.
 *
 * Displays a horizontal bar pinned to the bottom of the page
 * with cookie/license consent texts, checkboxes, and an Accept button.
 */
qx.Class.define("osparc.CookiePolicy", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(6));

    this.set({
      backgroundColor: "background-main-1",
      padding: 10,
      zIndex: 1000,
    });

    this.__buildLayout();
  },

  events: {
    "cookiesAccepted": "qx.event.type.Event",
    "cookiesDeclined": "qx.event.type.Event"
  },

  statics: {
    COOKIES_ACCEPTED_NAME: "cookies_v0:accepted",

    areCookiesAccepted: function() {
      // testing purposes
      return false;
      // for master platforms, we consider cookies accepted by default
      const platformName = osparc.store.StaticInfo.getPlatformName();
      if (platformName === "master") {
        return true;
      }
      const cookiesAccepted = osparc.utils.Utils.cookie.getCookie(this.COOKIES_ACCEPTED_NAME);
      return (cookiesAccepted === "true");
    },

    acceptCookies: function() {
      const expirationDays = 60;
      osparc.utils.Utils.cookie.setCookie(this.COOKIES_ACCEPTED_NAME, true, expirationDays);
    },

    declineCookies: function() {
      osparc.utils.Utils.cookie.deleteCookie(this.COOKIES_ACCEPTED_NAME);
    },

    getITISPrivacyPolicyLink: function(linkText = "Privacy Policy") {
      const color = qx.theme.manager.Color.getInstance().resolve("text");
      const link = `<a href=https://itis.swiss/meta-navigation/privacy-policy/ style='color: ${color}' target='_blank'>${linkText}</a>`;
      return link;
    },

    getS4LPrivacyPolicyLink: function(linkText = "Privacy Policy") {
      const color = qx.theme.manager.Color.getInstance().resolve("text");
      const link = `<a href=https://sim4life.swiss/privacy/ style='color: ${color}' target='_blank'>${linkText}</a>`;
      return link;
    },

    getZMTEULALink: function(linkText = "end-users license agreement (EULA)") {
      const color = qx.theme.manager.Color.getInstance().resolve("text");
      const link = `<a href='https://zurichmedtech.github.io/s4l-manual/#/docs/licensing/copyright_Sim4Life?id=zurich-medtech-ag-zmt' style='color: ${color}' target='_blank''>${linkText}</a>`;
      return link;
    }
  },

  members: {
    __createRow: function(label, checkBox) {
      const row = new qx.ui.container.Composite(new qx.ui.layout.HBox(8).set({
        alignY: "middle"
      }));
      row.add(label, {
        flex: 1
      });
      row.add(checkBox);
      return row;
    },

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "cookie-text": {
          const link = osparc.CookiePolicy.getITISPrivacyPolicyLink("Privacy Policy");
          const text = this.tr("This website applies cookies to personalize your experience and to make our site easier to navigate. By visiting the site, you agree to the ") + link + ".";
          control = new qx.ui.basic.Label(text).set({
            rich: true
          });
          break;
        }
        case "cookie-text-s4l": {
          const link = osparc.CookiePolicy.getS4LPrivacyPolicyLink("Privacy Policy");
          const text = this.tr("This website applies cookies to personalize your experience and to make our site easier to navigate. By visiting the site, you agree to the ") + link + ".";
          control = new qx.ui.basic.Label(text).set({
            rich: true
          });
          break;
        }
        case "accept-cookie":
          control = new qx.ui.form.CheckBox().set({
            value: true
          });
          break;
        case "license-text-s4llite": {
          control = new qx.ui.basic.Label().set({
            rich: true
          });
          const text = this.tr("By visiting the site, you agree to the ");
          const licenseLink = "https://zurichmedtech.github.io/s4l-lite-manual/#/docs/licensing/copyright_Sim4Life?id=zurich-medtech-ag-zmt";
          const color = qx.theme.manager.Color.getInstance().resolve("text");
          const textLink = `<a href=${licenseLink} style='color: ${color}' target='_blank'>Licensing.</a>`;
          control.setValue(text + textLink);
          break;
        }
        case "license-text-s4l": {
          control = new qx.ui.basic.Label().set({
            rich: true
          });
          const text = this.tr("By visiting the site, you agree to the ");
          const licenseLink = "https://zurichmedtech.github.io/s4l-manual/#/docs/licensing/copyright_Sim4Life?id=zurich-medtech-ag-zmt";
          const color = qx.theme.manager.Color.getInstance().resolve("text");
          const textLink = `<a href=${licenseLink} style='color: ${color}' target='_blank'>Licensing.</a>`;
          control.setValue(text + textLink);
          break;
        }
        case "accept-license":
          control = new qx.ui.form.CheckBox().set({
            value: true
          });
          break;
        case "license-text-2": {
          const text = this.tr("It also uses third party software and libraries. By visiting the site, you agree to the ");
          control = new qx.ui.basic.Label(text).set({
            rich: true
          });
          const licenseLink = osparc.store.Support.getLicenseURL();
          const lbl = control.getValue();
          if (licenseLink) {
            const color = qx.theme.manager.Color.getInstance().resolve("text");
            const textLink = `<a href=${licenseLink} style='color: ${color}' target='_blank'>Licensing.</a>`;
            control.setValue(lbl + textLink);
          } else {
            control.setValue(lbl + this.tr("Licensing."));
          }
          break;
        }
        case "accept-license-2":
          control = new qx.ui.form.CheckBox().set({
            value: true
          });
          break;
        case "accept-button": {
          control = new qx.ui.form.Button(this.tr("Accept")).set({
            allowGrowX: false,
            alignX: "right"
          });
          osparc.utils.Utils.setIdToWidget(control, "acceptCookiesBtn");
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      const checkButtons = [];

      // Cookie consent row
      let cookieText;
      if (osparc.product.Utils.isS4LProduct()) {
        cookieText = this.getChildControl("cookie-text-s4l");
      } else {
        cookieText = this.getChildControl("cookie-text");
      }
      const acceptCookie = this.getChildControl("accept-cookie");
      checkButtons.push(acceptCookie);
      this._add(this.__createRow(cookieText, acceptCookie));

      // License rows (product-specific)
      if (osparc.product.Utils.showLicenseExtra()) {
        let licenseText;
        if (osparc.product.Utils.isProduct("s4llite")) {
          licenseText = this.getChildControl("license-text-s4llite");
        } else {
          licenseText = this.getChildControl("license-text-s4l");
        }
        const acceptLicense = this.getChildControl("accept-license");
        checkButtons.push(acceptLicense);
        this._add(this.__createRow(licenseText, acceptLicense));

        const licenseText2 = this.getChildControl("license-text-2");
        const acceptLicense2 = this.getChildControl("accept-license-2");
        checkButtons.push(acceptLicense2);
        this._add(this.__createRow(licenseText2, acceptLicense2));
      }

      // Accept button
      const acceptBtn = this.getChildControl("accept-button");
      this._add(acceptBtn);

      const evalAcceptButton = () => {
        acceptBtn.setEnabled(checkButtons.every(checkButton => checkButton.getValue()));
      };
      checkButtons.forEach(checkButton => checkButton.addListener("changeValue", () => evalAcceptButton()));
      acceptBtn.addListener("execute", () => this.fireEvent("cookiesAccepted"), this);
      evalAcceptButton();
    }
  }
});
