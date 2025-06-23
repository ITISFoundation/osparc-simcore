/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2025 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Odei Maiz (odeimaiz)
 */

qx.Class.define("osparc.share.RequestServiceAccess", {
  extend: qx.ui.core.Widget,

  construct: function(cantReadServicesData) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(25));

    this.__populateLayout(cantReadServicesData);
  },

  statics: {
    openRequestAccess: function(cantReadServicesData) {
      const requestServiceAccess = new osparc.share.RequestServiceAccess(cantReadServicesData);
      const caption = qx.locale.Manager.tr("Request Apps Access");
      osparc.ui.window.Window.popUpInWindow(requestServiceAccess, caption, 600, 400).set({
        clickAwayClose: false,
        resizable: true,
        showClose: true
      });
    }
  },

  members: {
    __populateLayout: function(cantReadServicesData) {
      const text = this.tr("In order to open the project, the following users/groups need to give you access to some apps. Please contact the app owner:");
      this._add(new qx.ui.basic.Label().set({
        value: text,
        font: "text-14",
        rich: true,
        wrap: true
      }));

      const grid = new qx.ui.layout.Grid(20, 10);
      const layout = new qx.ui.container.Composite(grid);
      this._add(layout);

      // Header
      layout.add(new qx.ui.basic.Label(this.tr("Owner")), {
        row: 0,
        column: 0
      });
      layout.add(new qx.ui.basic.Label(this.tr("Email")), {
        row: 0,
        column: 1
      });
      layout.add(new qx.ui.basic.Label(this.tr("App")), {
        row: 0,
        column: 2
      });

      // Populate the grid with the cantReadServicesData
      cantReadServicesData.forEach((cantReadServiceData, idx) => {
        const userGroupId = cantReadServiceData["owner"];
        if (userGroupId) {
          const username = new qx.ui.basic.Label().set({
            rich: true,
            selectable: true,
          });
          layout.add(username, {
            row: idx+1,
            column: 0
          });
          const email = new qx.ui.basic.Label().set({
            rich: true,
            selectable: true,
          });
          layout.add(email, {
            row: idx+1,
            column: 1
          });
          const appLabel = new qx.ui.basic.Label().set({
            value: `${cantReadServiceData["key"]}:${osparc.service.Utils.extractVersionDisplay(cantReadServiceData["release"])}`,
            rich: true,
            selectable: true,
          });
          layout.add(appLabel, {
            row: idx+1,
            column: 2
          });

          osparc.store.Users.getInstance().getUser(userGroupId)
            .then(user => {
              username.setValue(user ? user.getLabel() : this.tr("Unknown user"));
              email.setValue(user ? user.getEmail() : "Unknown email");
            })
            .catch(() => {
              username.setValue(this.tr("Unknown user"));
              email.setValue("Unknown email");
            });
        }
      });
    }
  }
});
