/**
 *  Main Authentication View
 *
*/
qx.Class.define("qxapp.auth.AuthView", {
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
    let reset = new qxapp.auth.ui.ResetPassPage();

    pages.add(login);
    pages.add(register);
    pages.add(reset);

    this._add(pages, {
      row:0,
      column:0
    });

    // Connections
    login.addListener("done", function(msg) {
      // if msg, flash it
      login.resetValues();
      this.fireDataEvent("done", msg);
    }, this);

    login.addListener("toReset", function(e) {
      pages.setSelection([reset]);
      login.resetValues();
    }, this);

    login.addListener("toRegister", function(e) {
      pages.setSelection([register]);
      login.resetValues();
    }, this);

    [register, reset].forEach(srcPage => {
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
