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

qx.Class.define("osparc.desktop.preferences.Preferences", {
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
      resizable: false,
      appearance: "service-window"
    });
    const closeBtn = this.getChildControl("close-button");
    osparc.utils.Utils.setIdToWidget(closeBtn, "preferencesWindowCloseBtn");

    const tabView = new qx.ui.tabview.TabView().set({
      barPosition: "left"
    });

    const profPage = new osparc.desktop.preferences.pages.ProfilePage();
    const profBtn = profPage.getChildControl("button");
    osparc.utils.Utils.setIdToWidget(profBtn, "preferencesProfileTabBtn");
    tabView.add(profPage);

    const secPage = new osparc.desktop.preferences.pages.SecurityPage();
    const secBtn = secPage.getChildControl("button");
    osparc.utils.Utils.setIdToWidget(secBtn, "preferencesSecurityTabBtn");
    tabView.add(secPage);

    const expPage = new osparc.desktop.preferences.pages.ExperimentalPage();
    const expBtn = expPage.getChildControl("button");
    osparc.utils.Utils.setIdToWidget(expBtn, "preferencesExperimentalTabBtn");
    tabView.add(expPage);

    const labelsPage = new osparc.desktop.preferences.pages.LabelsPage();
    tabView.add(labelsPage);

    this.add(tabView, {
      flex: 1
    });
  }

});
