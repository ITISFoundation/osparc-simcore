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
      layout: new qx.ui.layout.VBox(),
      allowMinimize: false,
      allowMaximize: false,
      showMinimize: false,
      showMaximize: false,
      autoDestroy: true,
      modal: true,
      width: 262,
      maxHeight: 500,
      clickAwayClose: true
    });

    this.__populateLayout(shareesData);

    this.center();
    this.open();
  },

  members: {
    __populateLayout: function(shareesData) {
      console.log(shareesData);
      const text = this.tr("The following users will not be able to open the shared study:");
      this.add(new qx.ui.basic.Label().set({
        value: text,
        font: "text-14",
        rich: true,
        wrap: true
      }));

      const grid = new qx.ui.layout.Grid(10, 6);
      Object.values(this.self().GridPos).forEach(gridPos => {
        grid.setColumnAlign(gridPos, "left", "middle");
      });
      grid.setColumnFlex(this.self().GridPos.reference, 1);
      const layout = new qx.ui.container.Composite(grid);
      this.add(layout);
      for (let i=0; i<shareesData.length; i++) {
        const shareeData = shareesData[i];
        osparc.store.Store.getInstance().getGroup(shareeData.gid)
          .then(group => {
            if (group) {
              console.log(group);
              layout.add(new qx.ui.basic.Label(text), {
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
