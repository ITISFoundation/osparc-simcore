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

    this._setLayout(new qx.ui.layout.HBox(10).set({
      alignY: "middle"
    }));

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
    },

    /**
     * Shows a modal footer banner with blocker overlay on the given application
     */
    popUpCookieBanner: function() {
      const root = qx.core.Init.getApplication().getRoot();
      const cookiePolicy = new osparc.CookiePolicy();
      // Semi-transparent blocker to make the banner modal
      const blocker = new qx.ui.core.Widget();
      blocker.set({
        backgroundColor: "background-main-1",
        opacity: 0.5,
        zIndex: 999
      });
      root.add(blocker, {
        top: 0,
        bottom: 0,
        left: 0,
        right: 0
      });
      root.add(cookiePolicy, {
        bottom: 0,
        left: 0,
        right: 0
      });
      const removeBanner = () => {
        root.remove(blocker);
        blocker.dispose();
        root.remove(cookiePolicy);
        cookiePolicy.dispose();
      };
      cookiePolicy.addListener("cookiesAccepted", () => {
        osparc.CookiePolicy.acceptCookies();
        removeBanner();
      });
      cookiePolicy.addListener("cookiesDeclined", () => {
        osparc.CookiePolicy.declineCookies();
        removeBanner();
      });
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "grid-container": {
          const grid = new qx.ui.layout.Grid(8, 4);
          grid.setColumnFlex(0, 1);
          grid.setColumnAlign(0, "right", "middle");
          control = new qx.ui.container.Composite(grid);
          break;
        }
        case "cookie-text": {
          const link = osparc.CookiePolicy.getITISPrivacyPolicyLink("Privacy Policy");
          const text = this.tr("This website applies cookies to personalize your experience and to make our site easier to navigate. By visiting the site, you agree to the ") + link + ".";
          control = new qx.ui.basic.Label(text).set({
            rich: true,
            wrap: true,
            textAlign: "right",
          });
          break;
        }
        case "cookie-text-s4l": {
          const link = osparc.CookiePolicy.getS4LPrivacyPolicyLink("Privacy Policy");
          const text = this.tr("This website applies cookies to personalize your experience and to make our site easier to navigate. By visiting the site, you agree to the ") + link + ".";
          control = new qx.ui.basic.Label(text).set({
            rich: true,
            wrap: true,
            textAlign: "right",
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
            rich: true,
            wrap: true,
            textAlign: "right",
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
            rich: true,
            wrap: true,
            textAlign: "right",
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
            rich: true,
            wrap: true,
            textAlign: "right",
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
            allowGrowY: false,
            alignY: "middle",
            appearance: "strong-button",
          });
          osparc.utils.Utils.setIdToWidget(control, "acceptCookiesBtn");
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      const checkButtons = [];
      let row = 0;

      const gridContainer = this.getChildControl("grid-container");

      // Cookie consent row
      let cookieText;
      if (osparc.product.Utils.isS4LProduct()) {
        cookieText = this.getChildControl("cookie-text-s4l");
      } else {
        cookieText = this.getChildControl("cookie-text");
      }
      const acceptCookie = this.getChildControl("accept-cookie");
      checkButtons.push(acceptCookie);
      gridContainer.add(cookieText, { column: 0, row });
      gridContainer.add(acceptCookie, { column: 1, row });
      row++;

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
        gridContainer.add(licenseText, { column: 0, row });
        gridContainer.add(acceptLicense, { column: 1, row });
        row++;

        const licenseText2 = this.getChildControl("license-text-2");
        const acceptLicense2 = this.getChildControl("accept-license-2");
        checkButtons.push(acceptLicense2);
        gridContainer.add(licenseText2, { column: 0, row });
        gridContainer.add(acceptLicense2, { column: 1, row });
      }

      // Spacer pushes everything to the right
      this._add(new qx.ui.core.Spacer(), { flex: 100 });
      // Grid takes available space, labels wrap on narrow screens
      this._add(gridContainer, { flex: 1 });
      // Accept button next to checkboxes
      const acceptBtn = this.getChildControl("accept-button");
      this._add(acceptBtn);
      this._add(new qx.ui.core.Spacer(), { flex: 100 });

      const evalAcceptButton = () => {
        acceptBtn.setEnabled(checkButtons.every(checkButton => checkButton.getValue()));
      };
      checkButtons.forEach(checkButton => checkButton.addListener("changeValue", () => evalAcceptButton()));
      acceptBtn.addListener("execute", () => this.fireEvent("cookiesAccepted"), this);
      evalAcceptButton();
    }
  }
});
