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
 *  Main Authentication View:
 *    A multi-page view that fills all page
 *
*/
qx.Class.define("qxapp.auth.MainView", {
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

    let login = new qxapp.auth.ui.LoginPage();
    let register = new qxapp.auth.ui.RegistrationPage();
    let resetRequest = new qxapp.auth.ui.ResetPassRequestPage();
    let reset = new qxapp.auth.ui.ResetPassPage();

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
  },

  /*
  *****************************************************************************
     EVENTS
  *****************************************************************************
  */

  events: {
    "done": "qx.event.type.Data"
  }
});
