/* ************************************************************************

   qxapp - the simcore frontend

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

qx.Class.define("qxapp.auth.LoginPage", {
  extend : qx.ui.core.Widget,

  /*
  *****************************************************************************
     CONSTRUCTOR
  *****************************************************************************
  */
  construct: function() {
    this.base(arguments);

    // Layout guarantees it gets centered in parent's page
    let layout = new qx.ui.layout.Grid();
    layout.setRowFlex(0, 1);
    layout.setColumnFlex(0, 1);
    this._setLayout(layout);

    // Pages
    let pages = new qx.ui.container.Stack().set({
      allowGrowX: false,
      allowGrowY: false,
      alignX: "center"
    });

    let login = new qxapp.auth.ui.LoginView();
    let register = new qxapp.auth.ui.RegistrationView();
    let resetRequest = new qxapp.auth.ui.ResetPassRequestView();
    let reset = new qxapp.auth.ui.ResetPassView();

    pages.add(login);
    pages.add(register);
    pages.add(resetRequest);
    pages.add(reset);

    this._add(pages, {
      row:0,
      column:0
    });

    const page = qxapp.auth.core.Utils.findParameterInFragment("page");
    const code = qxapp.auth.core.Utils.findParameterInFragment("code");
    if (page === "reset-password" && code !== null) {
      pages.setSelection([reset]);
    }

    const urlFragment = qxapp.utils.Utils.parseURLFragment();
    if (urlFragment.nav && urlFragment.nav.length) {
      if (urlFragment.nav[0] === "registration") {
        pages.setSelection([register]);
      } else if (urlFragment.nav[0] === "reset-password") {
        pages.setSelection([reset]);
      }
    } else if (urlFragment.params && urlFragment.params.registered) {
      qxapp.component.message.FlashMessenger.getInstance().logAs(this.tr("Your account has been created.<br>You can now use your credentials to login."));
    }

    // Transitions between pages
    login.addListener("done", function(msg) {
      login.resetValues();
      this.fireDataEvent("done", msg);
    }, this);

    login.addListener("toReset", function(e) {
      pages.setSelection([resetRequest]);
      login.resetValues();
    }, this);

    login.addListener("toRegister", function(e) {
      pages.setSelection([register]);
      login.resetValues();
    }, this);

    [register, resetRequest, reset].forEach(srcPage => {
      srcPage.addListener("done", function(msg) {
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

      const platformVersion = qxapp.utils.LibVersions.getPlatformVersion();
      if (platformVersion) {
        const text = platformVersion.name + " v" + platformVersion.version;
        const versionLink = new qxapp.ui.basic.LinkLabel(text, platformVersion.url).set({
          font: "text-12",
          textColor: "text-darker"
        });
        versionLinkLayout.add(versionLink);

        const separator = new qx.ui.basic.Label("::");
        versionLinkLayout.add(separator);
      }

      const organizationLink = new qxapp.ui.basic.LinkLabel("© 2019 IT'IS Foundation", "https://itis.swiss").set({
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
