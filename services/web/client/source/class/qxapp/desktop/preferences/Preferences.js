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

/** Application's preferences
 *
 *  - multi-page modal window
 *
*/

qx.Class.define("qxapp.desktop.preferences.Preferences", {
  extend: qx.ui.window.Window,

  construct: function() {
    this.base(arguments, this.tr("Preferences"));
    this.set({
      layout: new qx.ui.layout.VBox(10),
      modal: true,
      width: 500,
      height: 500 * 1.2,
      showClose: true,
      showMaximize: false,
      showMinimize: false,
      resizable: false
    });
    const closeBtn = this.getChildControl("close-button");
    qxapp.utils.Utils.setIdToWidget(closeBtn, "preferencesWindowCloseBtn");

    const tabView = new qx.ui.tabview.TabView().set({
      barPosition: "left"
    });

    const profPage = new qxapp.desktop.preferences.pages.ProfilePage();
    const profBtn = profPage.getChildControl("button");
    qxapp.utils.Utils.setIdToWidget(profBtn, "preferencesProfileTabBtn");
    tabView.add(profPage);

    const secPage = new qxapp.desktop.preferences.pages.SecurityPage();
    const secBtn = secPage.getChildControl("button");
    qxapp.utils.Utils.setIdToWidget(secBtn, "preferencesSecurityTabBtn");
    tabView.add(secPage);

    const expPage = new qxapp.desktop.preferences.pages.ExperimentalPage();
    const expBtn = expPage.getChildControl("button");
    qxapp.utils.Utils.setIdToWidget(expBtn, "preferencesExperimentalTabBtn");
    tabView.add(expPage);

    this.add(tabView, {
      flex: 1
    });
  }

});
