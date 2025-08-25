/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.admin.Maintenance", {
  extend: osparc.po.BaseView,

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "maintenance-container": {
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
          this._add(control, {
            flex: 1
          });
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    _buildLayout: function() {
      osparc.data.Resources.get("maintenance")
        .then(scheduledMaintenance => {
          if (scheduledMaintenance) {
            this.__populateMaintenanceLayout(JSON.parse(scheduledMaintenance))
          } else {
            this.__populateMaintenanceLayout(null)
          }
        })
        .catch(err => console.error(err));
    },

    __populateMaintenanceLayout: function(data) {
      const vBox = this.getChildControl("maintenance-container");
      vBox.removeAll();

      if (data) {
        const displayMaintenanceBtn = new qx.ui.form.Button(this.tr("Test Maintenance message")).set({
          appearance: "strong-button",
          allowGrowX: false,
        });
        const message = osparc.MaintenanceTracker.dataToText(new Date(data["start"]), new Date(data["end"]), data["reason"]);
        displayMaintenanceBtn.addListener("execute", () => osparc.MaintenanceTracker.getInstance().messageToRibbon(true), message);
        vBox.add(displayMaintenanceBtn);

        const respLabel = new qx.ui.basic.Label(this.tr("Start and End dates go in UTC time zone"));
        vBox.add(respLabel);

        const invitationRespViewer = new osparc.ui.basic.JsonTreeWidget(data, "maintenance-data");
        const container = new qx.ui.container.Scroll();
        container.add(invitationRespViewer);
        vBox.add(container, {
          flex: 1
        });
      } else {
        const label = new qx.ui.basic.Label().set({
          value: this.tr("No Maintenance scheduled")
        });
        vBox.add(label);
      }
    }
  }
});
