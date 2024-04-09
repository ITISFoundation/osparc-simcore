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
  type: "abstract",

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
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "main-layout": {
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
            alignX: "center",
            alignY: "middle"
          });
          const scrollView = new qx.ui.container.Scroll();
          scrollView.add(control);
          break;
        }
        case "top-spacer":
          control = new qx.ui.core.Spacer().set({
            minHeight: 50
          });
          this.getChildControl("main-layout").add(control, {
            flex: 1
          });
          break;
        case "logo-w-platform":
          control = new osparc.ui.basic.LogoWPlatform();
          control.setSize({
            width: 300,
            height: 90
          });
          control.setFont("text-18");
          this.getChildControl("main-layout").add(control);
          break;
        case "science-text-image":
          control = new qx.ui.basic.Image("osparc/Sim4Life_science_Subline.svg").set({
            width: 300,
            height: 24,
            scale: true,
            alignX: "center",
            marginTop: -25
          });
          this.getChildControl("main-layout").add(control);
          break;
        case "pages-stack":
          control = new qx.ui.container.Stack().set({
            allowGrowX: false,
            alignX: "center"
          });
          this.getChildControl("main-layout").add(control, {
            flex: 1
          });
          break;
        case "bottom-spacer":
          control = new qx.ui.core.Spacer().set({
            minHeight: 50
          });
          this.getChildControl("main-layout").add(control, {
            flex: 1
          });
          break;
        case "footer": {
          control = this.__getVersionLink();
          this.getChildControl("main-layout").add(control);
          break;
        }
        case "login-view": {
          control = new osparc.auth.ui.LoginView();
          this.getChildControl("pages-stack").add(control);
          break;
        }
        case "registration-view": {
          control = new osparc.auth.ui.RegistrationView();
          this.getChildControl("pages-stack").add(control);
          break;
        }
        case "request-account": {
          control = new osparc.auth.ui.RequestAccount();
          this.getChildControl("pages-stack").add(control);
          break;
        }
        case "verify-phone-number-view": {
          control = new osparc.auth.ui.VerifyPhoneNumberView();
          this.getChildControl("pages-stack").add(control);
          break;
        }
        case "reset-password-request-view": {
          control = new osparc.auth.ui.ResetPassRequestView();
          this.getChildControl("pages-stack").add(control);
          break;
        }
        case "reset-password-view": {
          control = new osparc.auth.ui.ResetPassView();
          this.getChildControl("pages-stack").add(control);
          break;
        }
        case "login-2FA-validation-code-view": {
          control = new osparc.auth.ui.Login2FAValidationCodeView();
          this.getChildControl("pages-stack").add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    _buildLayout: function() {
      throw new Error("Abstract method called!");
    },

    _setBackgroundImage: function(backgroundImage) {
      if (osparc.product.Utils.getProductName().includes("s4l")) {
        this.getContentElement().setStyles({
          "background-image": backgroundImage,
          "background-repeat": "no-repeat",
          "background-size": "65% auto, 80% auto", // auto width, 85% height
          "background-position": "left bottom, left -440px bottom -230px" // left bottom
        });
      } else {
        this.getContentElement().setStyles({
          "background-image": backgroundImage,
          "background-repeat": "no-repeat",
          "background-size": "50% auto", // 50% of the view width
          "background-position": "left 10% center" // left bottom
        });
      }
    },

    _resetBackgroundImage: function() {
      this.getContentElement().setStyles({
        "background-image": ""
      });
    },

    _getMainLayout: function() {
      const mainLayout = this.getChildControl("main-layout");
      this.getChildControl("top-spacer");
      this.getChildControl("logo-w-platform");
      if (osparc.product.Utils.isProduct("s4lacad")) {
        this.getChildControl("science-text-image");
      }
      this.__getLoginStack();
      this.getChildControl("bottom-spacer");
      this.getChildControl("footer");
      return mainLayout;
    },

    __getLoginStack: function() {
      const pages = this.getChildControl("pages-stack");

      const login = this.getChildControl("login-view");
      const registration = this.getChildControl("registration-view");
      const config = osparc.store.Store.getInstance().get("config");
      let requestAccount = null;
      if (config["invitation_required"] && osparc.product.Utils.isS4LProduct()) {
        requestAccount = this.getChildControl("request-account");
      }
      const verifyPhoneNumber = this.getChildControl("verify-phone-number-view");
      const resetPasswordRequest = this.getChildControl("reset-password-request-view");
      const resetPassword = this.getChildControl("reset-password-view");
      const login2FAValidationCode = this.getChildControl("login-2FA-validation-code-view");

      // styling
      pages.getChildren().forEach(page => {
        page.getChildren().forEach(child => {
          if ("getChildren" in child) {
            child.getChildren().forEach(c => {
              // "Create account" and "Forgot password"
              c.set({
                textColor: "#ddd"
              });
            });
          }
        });
      });

      const page = osparc.auth.core.Utils.findParameterInFragment("page");
      const code = osparc.auth.core.Utils.findParameterInFragment("code");
      if (page === "reset-password" && code !== null) {
        pages.setSelection([resetPassword]);
      }

      const urlFragment = osparc.utils.Utils.parseURLFragment();
      if (urlFragment.nav && urlFragment.nav.length) {
        if (urlFragment.nav[0] === "registration") {
          pages.setSelection([registration]);
        } else if (urlFragment.nav[0] === "request-account" && requestAccount) {
          pages.setSelection([requestAccount]);
        } else if (urlFragment.nav[0] === "reset-password") {
          pages.setSelection([resetPassword]);
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
        pages.setSelection([registration]);
        login.resetValues();
      }, this);

      if (requestAccount) {
        login.addListener("toRequestAccount", () => {
          pages.setSelection([requestAccount]);
          login.resetValues();
        }, this);
      }

      login.addListener("toReset", () => {
        pages.setSelection([resetPasswordRequest]);
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

      registration.addListener("done", msg => {
        osparc.utils.Utils.cookie.deleteCookie("user");
        this.fireDataEvent("done", msg);
      });

      if (requestAccount) {
        requestAccount.addListener("done", msg => {
          osparc.utils.Utils.cookie.deleteCookie("user");
          this.fireDataEvent("done", msg);
        });
      }

      verifyPhoneNumber.addListener("done", msg => {
        login.resetValues();
        this.fireDataEvent("done", msg);
      }, this);

      [resetPasswordRequest, resetPassword].forEach(srcPage => {
        srcPage.addListener("done", msg => {
          pages.setSelection([login]);
          srcPage.resetValues();
        }, this);
      });

      return pages;
    },

    __getVersionLink: function() {
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
      const rData = osparc.store.StaticInfo.getInstance().getReleaseData();
      const platformVersion = osparc.utils.LibVersions.getPlatformVersion();
      let text = "osparc-simcore ";
      text += (rData["tag"] && rData["tag"] !== "latest") ? rData["tag"] : platformVersion.version;
      const platformName = osparc.store.StaticInfo.getInstance().getPlatformName();
      text += platformName.length ? ` (${platformName})` : "";
      const url = rData["url"] || osparc.utils.LibVersions.getVcsRefUrl();
      versionLink.set({
        value: text,
        url
      });
      versionLinkLayout.add(versionLink);

      const organizationLink = new osparc.ui.basic.LinkLabel().set({
        textColor: "text-darker"
      });
      const vendor = osparc.store.VendorInfo.getInstance().getVendor();
      if (vendor && "url" in vendor && "copyright" in vendor) {
        organizationLink.set({
          value: vendor.copyright,
          url: vendor.url
        });
      }
      versionLinkLayout.add(organizationLink);

      versionLinkLayout.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      return versionLinkLayout;
    }
  }
});
