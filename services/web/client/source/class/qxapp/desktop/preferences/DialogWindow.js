/** Application's preferences
 *
 *  - multi-page modal window
 *
*/
/* eslint no-warning-comments: "off" */
qx.Class.define("qxapp.desktop.preferences.DialogWindow", {
  extend: qx.ui.window.Window,

  construct: function() {
    this.base(arguments, this.tr("Preferences"));
    this.set({
      modal: true,
      width: 500,
      height: 500 * 1.2,
      showClose: true,
      showMaximize: false,
      showMinimize: false,
      resizable: false
    });
    this.setLayout(new qx.ui.layout.VBox(10));

    let tabView = new qx.ui.tabview.TabView().set({
      barPosition: "left"
    });
    tabView.add(new qxapp.desktop.preferences.pages.ProfilePage());
    tabView.add(new qxapp.desktop.preferences.pages.SecurityPage());
    tabView.add(new qxapp.desktop.preferences.pages.ExperimentalPage());

    this.add(tabView, {
      flex: 1
    });
  }

});
