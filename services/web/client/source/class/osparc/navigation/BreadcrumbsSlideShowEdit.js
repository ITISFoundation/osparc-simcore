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
    "removeService": "qx.event.type.Data"
  },

  members: {
    populateButtons: function(nodesIds = []) {
      this._removeAll();

      let newServiceBtn = this.__createNewServiceBtn();
      newServiceBtn.leftNodeId = null;
      this._add(newServiceBtn);

      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const slideShow = study.getUi().getSlideshow().getData();

      nodesIds.forEach(nodeId => {
        newServiceBtn.rightNodeId = nodeId;

        const node = study.getWorkbench().getNode(nodeId);
        if (node && nodeId in slideShow) {
          const btn = new qx.ui.toolbar.MenuButton().set({
            paddingLeft: 5,
            paddingRight: 5,
            marginLeft: 1,
            marginRight: 1
          });
          this._add(btn);

          const pos = slideShow[nodeId].position;
          node.bind("label", btn, "label", {
            converter: val => `${pos+1}- ${val}`
          });

          const menu = this.__createEditNodeMenu(nodeId);
          btn.setMenu(menu);

          newServiceBtn = this.__createNewServiceBtn();
          newServiceBtn.leftNodeId = nodeId;
          newServiceBtn.rightNodeId = null;
          this._add(newServiceBtn);
        }
      });
    },

    __createNewServiceBtn: function() {
      const newServiceBtn = new qx.ui.form.Button().set({
        ...osparc.navigation.NavigationBar.BUTTON_OPTIONS,
        icon: "@FontAwesome5Solid/plus-circle/24",
        textColor: "ready-green"
      });
      newServiceBtn.getContentElement()
        .setStyles({
          "border-radius": "24px"
        });
      newServiceBtn.addListener("execute", () => {
        this.fireDataEvent("addServiceBetween", {
          leftNodeId: newServiceBtn.leftNodeId,
          rightNodeId: newServiceBtn.rightNodeId
        });
      });
      return newServiceBtn;
    },

    __createEditNodeMenu: function(nodeId) {
      const menu = new qx.ui.menu.Menu();

      const deleteButton = new qx.ui.menu.Button("Delete");
      deleteButton.addListener("execute", () => {
        this.fireDataEvent("removeService", nodeId);
      });
      menu.add(deleteButton);

      return menu;
    }
  }
});
