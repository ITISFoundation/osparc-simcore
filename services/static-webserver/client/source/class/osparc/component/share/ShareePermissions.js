/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2023 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Odei Maiz (odeimaiz)
 */

qx.Class.define("osparc.component.share.ShareePermissions", {
  extend: osparc.ui.window.SingletonWindow,
  construct: function(shareesData) {
    this.base(arguments, "collaboratorsManager", this.tr("Sharee permissions"));
    this.set({
      layout: new qx.ui.layout.VBox(20),
      allowMinimize: false,
      allowMaximize: false,
      showMinimize: false,
      showMaximize: false,
      autoDestroy: true,
      modal: true,
      width: 500,
      maxHeight: 500,
      clickAwayClose: true
    });

    this.__populateLayout(shareesData);

    this.center();
    this.open();
  },

  members: {
    __populateLayout: function(shareesData) {
      const text = this.tr("The following users/groups will not be able to open the shared study:");
      this.add(new qx.ui.basic.Label().set({
        value: text,
        font: "text-14",
        rich: true,
        wrap: true
      }));

      const grid = new qx.ui.layout.Grid(20, 10);
      const layout = new qx.ui.container.Composite(grid);
      this.add(layout);
      for (let i=0; i<shareesData.length; i++) {
        const shareeData = shareesData[i];
        osparc.store.Store.getInstance().getGroup(shareeData.gid)
          .then(group => {
            if (group) {
              layout.add(new qx.ui.basic.Label(group.label), {
                row: i,
                column: 0
              });

              const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
              shareeData["inaccessible_services"].forEach(inaccessibleService => {
                const metaData = osparc.utils.Services.getMetaData(inaccessibleService.key, inaccessibleService.version);
                vBox.add(new qx.ui.basic.Label(metaData.name + " : " + metaData.version));
              });
              layout.add(vBox, {
                row: i,
                column: 1
              });
            }
          });
      }
    }
  }
});
