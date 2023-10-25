/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.desktop.MainPageDesktop", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(null, null, "separator-vertical"));

    this._add(osparc.notification.RibbonNotifications.getInstance());

    const navBar = new osparc.navigation.NavigationBar();
    this._add(navBar);

    osparc.MaintenanceTracker.getInstance().startTracker();

    const store = osparc.store.Store.getInstance();
    const preloadPromises = [];
    const walletsEnabled = osparc.desktop.credits.Utils.areWalletsEnabled();
    if (walletsEnabled) {
      preloadPromises.push(store.reloadCreditPrice());
      preloadPromises.push(store.reloadWallets());
    }
    preloadPromises.push(store.getAllClassifiers(true));
    preloadPromises.push(store.getTags());
    Promise.all(preloadPromises)
      .then(() => {
        const desktopCenter = new osparc.desktop.credits.DesktopCenter();
        this._add(desktopCenter, {
          flex: 1
        });
      });
  }
});
