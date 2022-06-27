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
      osparc.utils.LibVersions.getPlatformName()
        .then(platformName => {
          let image = null;
          const now = new Date().getTime();
          const afterKZ = new Date("2022-07-01").getTime();
          if ((now < afterKZ) && platformName === "master") {
            image = this._getLogoWPlatform2();
          } else {
            image = this._getLogoWPlatform();
          }
          this._add(image, {
            row: 0,
            column: 0
          });
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

    _getLogoWPlatform2: function() {
      const container = new qx.ui.container.Stack();
      [
        "osparc/kz_1.jpg",
        "osparc/kz_2.jpg",
        "osparc/kz_3.png",
        "osparc/kz_4.png"
      ].forEach((src, i) => {
        const layout = new qx.ui.container.Composite(new qx.ui.layout.HBox());
        layout.add(new qx.ui.core.Spacer(), {
          flex: 1
        });
        const image = new qx.ui.basic.Image(src).set({
          allowShrinkX: true,
          allowShrinkY: true,
          width: 300,
          height: 150,
          scale: true
        });
        image.addListener("tap", () => {
          const nextIdx = i === 3 ? 0 : i+1;
          container.setSelection([container.getSelectables()[nextIdx]]);
        });
        layout.add(image);
        layout.add(new qx.ui.core.Spacer(), {
          flex: 1
        });
        container.add(layout);
      });
      return container;
    },

    _getLoginStack: function() {
      const pages = new qx.ui.container.Stack().set({
        allowGrowX: false,
        allowGrowY: false,
        alignX: "center"
      });

      const login = new osparc.auth.ui.LoginView();
      const register = new osparc.auth.ui.RegistrationView();
      const resetRequest = new osparc.auth.ui.ResetPassRequestView();
      const reset = new osparc.auth.ui.ResetPassView();

      pages.add(login);
      pages.add(register);
      pages.add(resetRequest);
      pages.add(reset);

      const page = osparc.auth.core.Utils.findParameterInFragment("page");
      const code = osparc.auth.core.Utils.findParameterInFragment("code");
      if (page === "reset-password" && code !== null) {
        pages.setSelection([reset]);
      }

      const urlFragment = osparc.utils.Utils.parseURLFragment();
      if (urlFragment.nav && urlFragment.nav.length) {
        if (urlFragment.nav[0] === "registration") {
          pages.setSelection([register]);
        } else if (urlFragment.nav[0] === "reset-password") {
          pages.setSelection([reset]);
        }
      } else if (urlFragment.params && urlFragment.params.registered) {
        osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Your account has been created.<br>You can now use your credentials to login."));
      }

      // Transitions between pages
      login.addListener("done", msg => {
        login.resetValues();
        this.fireDataEvent("done", msg);
      }, this);

      login.addListener("toReset", e => {
        pages.setSelection([resetRequest]);
        login.resetValues();
      }, this);

      login.addListener("toRegister", e => {
        pages.setSelection([register]);
        login.resetValues();
      }, this);

      register.addListener("done", msg => {
        osparc.utils.Utils.cookie.deleteCookie("user");
        this.fireDataEvent("done", msg);
      });

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

      const platformVersion = osparc.utils.LibVersions.getPlatformVersion();
      if (platformVersion) {
        let text = platformVersion.name + " " + platformVersion.version;
        const versionLink = new osparc.ui.basic.LinkLabel(null, platformVersion.url).set({
          textColor: "text-darker"
        });
        versionLinkLayout.add(versionLink);

        const separator = new qx.ui.basic.Label("::");
        versionLinkLayout.add(separator);
        osparc.utils.LibVersions.getPlatformName()
          .then(platformName => {
            text += platformName.length ? ` (${platformName})` : " (production)";
          })
          .finally(() => {
            versionLink.setValue(text);
          });
      }

      const organizationLink = new osparc.ui.basic.LinkLabel(`© ${new Date().getFullYear()} IT'IS Foundation`, "https://itis.swiss").set({
        textColor: "text-darker"
      });
      versionLinkLayout.add(organizationLink);

      return versionLinkLayout;
    }
  }
});
