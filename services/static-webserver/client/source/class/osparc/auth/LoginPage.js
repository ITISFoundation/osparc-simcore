/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Pedro Crespo (pcrespov)

************************************************************************ */

/**
 *  Main Authentication Page:
 *    A multi-page view that fills all page
 */

qx.Class.define("osparc.auth.LoginPage", {
  extend: qx.ui.core.Widget,

  /*
  *****************************************************************************
     CONSTRUCTOR
  *****************************************************************************
  */
  construct: function() {
    this.base(arguments);

    this._buildLayout();
  },

  events: {
    "done": "qx.event.type.Data"
  },

  members: {
    _buildLayout: function() {
      // Layout guarantees it gets centered in parent's page
      const layout = new qx.ui.layout.Grid(20, 20);
      layout.setRowFlex(1, 1);
      layout.setColumnFlex(0, 1);
      this._setLayout(layout);

      const image = this._getLogoWPlatform();
      this._add(image, {
        row: 0,
        column: 0
      });

      const pages = this._getLoginStack();
      this._add(pages, {
        row: 1,
        column: 0
      });

      const versionLink = this._getVersionLink();
      this._add(versionLink, {
        row: 2,
        column: 0
      });
    },

    _getLogoWPlatform: function() {
      const image = new osparc.ui.basic.LogoWPlatform();
      image.setSize({
        width: 240,
        height: 120
      });
      image.setFont("text-18");
      return image;
    },

    _getLoginStack: function() {
      const pages = new qx.ui.container.Stack().set({
        allowGrowX: false,
        allowGrowY: false,
        alignX: "center"
      });

      const login = new osparc.auth.ui.LoginView();
      const register = new osparc.auth.ui.RegistrationView();
      const requestAccount = new osparc.auth.ui.RequestAccount();
      const verifyPhoneNumber = new osparc.auth.ui.VerifyPhoneNumberView();
      const resetRequest = new osparc.auth.ui.ResetPassRequestView();
      const reset = new osparc.auth.ui.ResetPassView();
      const login2FAValidationCode = new osparc.auth.ui.Login2FAValidationCodeView();

      pages.add(login);
      pages.add(register);
      pages.add(requestAccount);
      pages.add(verifyPhoneNumber);
      pages.add(resetRequest);
      pages.add(reset);
      pages.add(login2FAValidationCode);

      const page = osparc.auth.core.Utils.findParameterInFragment("page");
      const code = osparc.auth.core.Utils.findParameterInFragment("code");
      if (page === "reset-password" && code !== null) {
        pages.setSelection([reset]);
      }

      const urlFragment = osparc.utils.Utils.parseURLFragment();
      if (urlFragment.nav && urlFragment.nav.length) {
        if (urlFragment.nav[0] === "registration") {
          pages.setSelection([register]);
        } else if (urlFragment.nav[0] === "request-account") {
          pages.setSelection([requestAccount]);
        } else if (urlFragment.nav[0] === "reset-password") {
          pages.setSelection([reset]);
        }
      } else if (urlFragment.params && urlFragment.params.registered) {
        osparc.FlashMessenger.getInstance().logAs(this.tr("Your account has been created.<br>You can now use your credentials to login."));
      }

      // Transitions between pages
      login.addListener("done", msg => {
        login.resetValues();
        this.fireDataEvent("done", msg);
      }, this);

      login.addListener("toRegister", () => {
        pages.setSelection([register]);
        login.resetValues();
      }, this);

      login.addListener("toRequestAccount", () => {
        pages.setSelection([requestAccount]);
        login.resetValues();
      }, this);

      login.addListener("toReset", e => {
        pages.setSelection([resetRequest]);
        login.resetValues();
      }, this);

      login.addListener("toVerifyPhone", e => {
        verifyPhoneNumber.set({
          userEmail: e.getData()
        });
        pages.setSelection([verifyPhoneNumber]);
        login.resetValues();
      }, this);

      login.addListener("to2FAValidationCode", e => {
        const msg = e.getData();
        const startIdx = msg.indexOf("+");
        login2FAValidationCode.set({
          userEmail: login.getEmail(),
          userPhoneNumber: msg.substring(startIdx, msg.length)
        });
        pages.setSelection([login2FAValidationCode]);
        login.resetValues();
      }, this);

      verifyPhoneNumber.addListener("skipPhoneRegistration", e => {
        login2FAValidationCode.set({
          userEmail: e.getData(),
          userPhoneNumber: null
        });
        pages.setSelection([login2FAValidationCode]);
        login.resetValues();
      }, this);

      login2FAValidationCode.addListener("done", msg => {
        login.resetValues();
        this.fireDataEvent("done", msg);
      }, this);

      register.addListener("done", msg => {
        osparc.utils.Utils.cookie.deleteCookie("user");
        this.fireDataEvent("done", msg);
      });

      requestAccount.addListener("done", msg => {
        osparc.utils.Utils.cookie.deleteCookie("user");
        this.fireDataEvent("done", msg);
      });

      verifyPhoneNumber.addListener("done", msg => {
        login.resetValues();
        this.fireDataEvent("done", msg);
      }, this);

      [resetRequest, reset].forEach(srcPage => {
        srcPage.addListener("done", msg => {
          pages.setSelection([login]);
          srcPage.resetValues();
        }, this);
      });

      return pages;
    },

    _getVersionLink: function() {
      const versionLinkLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignX: "center"
      })).set({
        margin: [10, 0]
      });

      versionLinkLayout.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      const versionLink = new osparc.ui.basic.LinkLabel().set({
        textColor: "text-darker"
      });
      const staticInfo = osparc.store.StaticInfo.getInstance();
      staticInfo.getReleaseData()
        .then(rData => {
          if (rData) {
            const releaseDate = rData["date"];
            const releaseTag = rData["tag"];
            const releaseUrl = rData["url"];
            if (releaseDate && releaseTag && releaseUrl) {
              const date = osparc.utils.Utils.formatDate(new Date(releaseDate));
              versionLink.set({
                value: date + " (" + releaseTag + ")&nbsp",
                url: releaseUrl
              });
            }
          } else {
            // fallback to old style
            const platformVersion = osparc.utils.LibVersions.getPlatformVersion();
            versionLink.setUrl(platformVersion.url);
            let text = platformVersion.name + " " + platformVersion.version;
            staticInfo.getPlatformName()
              .then(platformName => {
                text += platformName.length ? ` (${platformName})` : " (production)";
              })
              .finally(() => {
                versionLink.setValue(text);
              });
          }
        });
      versionLinkLayout.add(versionLink);

      const organizationLink = new osparc.ui.basic.LinkLabel().set({
        textColor: "text-darker"
      });
      osparc.store.VendorInfo.getInstance().getVendor()
        .then(vendor => {
          if (vendor) {
            organizationLink.set({
              value: vendor.copyright,
              url: vendor.url
            });
          }
        });
      versionLinkLayout.add(organizationLink);

      versionLinkLayout.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      return versionLinkLayout;
    }
  }
});
