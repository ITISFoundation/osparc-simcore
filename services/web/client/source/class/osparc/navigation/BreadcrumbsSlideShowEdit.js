/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 *
 */

qx.Class.define("osparc.navigation.BreadcrumbsSlideShowEdit", {
  extend: osparc.navigation.BreadcrumbNavigation,

  events: {
    "addServiceBetween": "qx.event.type.Data",
    "removeServiceBetween": "qx.event.type.Data"
  },

  members: {
    populateButtons: function(nodesIds = []) {
      this._removeAll();

      let newServiceBtn = this.__createNewServiceBtn();
      this._add(newServiceBtn);

      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const slideShow = study.getUi().getSlideshow();

      nodesIds.forEach(nodeId => {
        const node = study.getWorkbench().getNode(nodeId);
        if (node && nodeId in slideShow) {
          const btn = new qx.ui.toolbar.MenuButton().set({
            marginLeft: 1,
            marginRight: 1
          });
          this._add(btn);

          const pos = slideShow[nodeId].position;
          node.bind("label", btn, "label", {
            converter: val => `${pos+1}- ${val}`
          });

          const menu = this.__createEditNodeMenu();
          btn.setMenu(menu);

          newServiceBtn.rightNodeId = nodeId;
          newServiceBtn = this.__createNewServiceBtn(nodeId);
          newServiceBtn.leftNodeId = nodeId;
          this._add(newServiceBtn);
        }
      });
    },

    __createNewServiceBtn: function() {
      const newServiceBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/plus-circle/24").set({
        ...osparc.navigation.NavigationBar.BUTTON_OPTIONS,
        textColor: "ready-green"
      });
      newServiceBtn.getContentElement()
        .setStyles({
          "border-radius": "24px"
        });
      newServiceBtn.addListener("execute", () => {
        console.log(newServiceBtn.leftNodeId);
        console.log(newServiceBtn.rightNodeId);
        this.fireDataEvent("addServiceBetween", {

        });
      });
      return newServiceBtn;
    },

    __createEditNodeMenu: function() {
      const menu = new qx.ui.menu.Menu();

      const deleteButton = new qx.ui.menu.Button("Delete");
      menu.add(deleteButton);

      const renameButton = new qx.ui.menu.Button("Rename");
      menu.add(renameButton);

      return menu;
    }
  }
});
