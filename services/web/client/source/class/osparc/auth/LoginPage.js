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
  extend : qx.ui.core.Widget,

  /*
  *****************************************************************************
     CONSTRUCTOR
  *****************************************************************************
  */
  construct: function() {
    this.base(arguments);

    // Layout guarantees it gets centered in parent's page
    const layout = new qx.ui.layout.Grid();
    layout.setRowFlex(0, 1);
    layout.setColumnFlex(0, 1);
    this._setLayout(layout);

    // Pages
    let pages = new qx.ui.container.Stack().set({
      allowGrowX: false,
      allowGrowY: false,
      alignX: "center"
    });

    let login = new osparc.auth.ui.LoginView();
    let register = new osparc.auth.ui.RegistrationView();
    let resetRequest = new osparc.auth.ui.ResetPassRequestView();
    let reset = new osparc.auth.ui.ResetPassView();

    pages.add(login);
    pages.add(register);
    pages.add(resetRequest);
    pages.add(reset);

    this._add(pages, {
      row:0,
      column:0
    });

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

    [register, resetRequest, reset].forEach(srcPage => {
      srcPage.addListener("done", msg => {
        pages.setSelection([login]);
        srcPage.resetValues();
      }, this);
    });

    this.__addVersionLink();
  },

  /*
  *****************************************************************************
     EVENTS
  *****************************************************************************
  */

  events: {
    "done": "qx.event.type.Data"
  },

  members: {
    __addVersionLink: function() {
      const versionLinkLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignX: "center"
      })).set({
        margin: [10, 0]
      });

      const platformVersion = osparc.utils.LibVersions.getPlatformVersion();
      if (platformVersion) {
        const text = platformVersion.name + " " + platformVersion.version;
        const versionLink = new osparc.ui.basic.LinkLabel(text, platformVersion.url).set({
          font: "text-12",
          textColor: "text-darker"
        });
        versionLinkLayout.add(versionLink);

        const separator = new qx.ui.basic.Label("::");
        versionLinkLayout.add(separator);
      }

      const organizationLink = new osparc.ui.basic.LinkLabel("© 2019 IT'IS Foundation", "https://itis.swiss").set({
        font: "text-12",
        textColor: "text-darker"
      });
      versionLinkLayout.add(organizationLink);

      this._add(versionLinkLayout, {
        row: 1,
        column: 0
      });
    }
  }
});
