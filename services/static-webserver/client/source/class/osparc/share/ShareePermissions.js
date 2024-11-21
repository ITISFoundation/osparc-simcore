/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2023 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Odei Maiz (odeimaiz)
 */

qx.Class.define("osparc.share.ShareePermissions", {
  extend: qx.ui.core.Widget,

  construct: function(shareesData) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(25));

    this.__populateLayout(shareesData);
  },

  members: {
    __populateLayout: function(shareesData) {
      const text = this.tr("The following users/groups will not be able to open the shared study, because they don't have access to some services. Please contact the service owner(s) to give permission.");
      this._add(new qx.ui.basic.Label().set({
        value: text,
        font: "text-14",
        rich: true,
        wrap: true
      }));

      const grid = new qx.ui.layout.Grid(20, 10);
      grid.setColumnAlign(0, "center", "middle");
      grid.setColumnAlign(1, "center", "middle");
      const layout = new qx.ui.container.Composite(grid);
      this._add(layout);
      for (let i=0; i<shareesData.length; i++) {
        const shareeData = shareesData[i];
        const group = osparc.store.Groups.getInstance().getGroup(shareeData.gid);
        if (group) {
          layout.add(new qx.ui.basic.Label(group.getLabel()), {
            row: i,
            column: 0
          });

          const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(8));
          shareeData["inaccessible_services"].forEach(inaccessibleService => {
            const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(5)).set({
              alignY: "middle"
            });
            const infoButton = new qx.ui.form.Button(null, "@MaterialIcons/info_outline/14");
            infoButton.setAppearance("strong-button");
            const label = new qx.ui.basic.Label();
            hBox.add(infoButton);
            hBox.add(label);
            osparc.store.Services.getService(inaccessibleService.key, inaccessibleService.version)
              .then(metadata => {
                label.setValue(metadata["name"] + " : " + metadata["version"])
                infoButton.addListener("execute", () => {
                  metadata["resourceType"] = "service";
                  const resourceDetails = new osparc.dashboard.ResourceDetails(metadata);
                  osparc.dashboard.ResourceDetails.popUpInWindow(resourceDetails);
                }, this);
              })

            vBox.add(hBox);
          });
          layout.add(vBox, {
            row: i,
            column: 1
          });
        }
      }
    }
  }
});
