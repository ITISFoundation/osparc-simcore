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

/** Application's preferences
 *
 *  - multi-page modal window
 *
*/

qx.Class.define("osparc.desktop.preferences.DialogWindow", {
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
    tabView.add(new osparc.desktop.preferences.pages.ProfilePage());
    tabView.add(new osparc.desktop.preferences.pages.SecurityPage());
    tabView.add(new osparc.desktop.preferences.pages.ExperimentalPage());

    this.add(tabView, {
      flex: 1
    });
  }

});
