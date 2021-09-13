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
    "removeNode": "qx.event.type.Data",
    "showNode": "qx.event.type.Data",
    "hideNode": "qx.event.type.Data"
  },

  members: {
    populateButtons: function(study) {
      this._removeAll();

      if (!study.getWorkbench().isPipelineLinear()) {
        return;
      }
      const nodeIds = study.getWorkbench().getPipelineLinearSorted();
      if (nodeIds === null) {
        return;
      }

      let newServiceBtn = this.__createNewServiceBtn();
      newServiceBtn.leftNodeId = null;
      this._add(newServiceBtn);

      const slideShow = study.getUi().getSlideshow();
      let currentPos = 0;
      nodeIds.forEach((nodeId, i) => {
        newServiceBtn.rightNodeId = nodeId;
        if (!study.getWorkbench().getNode(nodeId).hasInputs()) {
          newServiceBtn.exclude();
        }

        const btn = new qx.ui.toolbar.MenuButton().set({
          paddingLeft: 5,
          paddingRight: 5,
          marginLeft: 1,
          marginRight: 1
        });
        this._add(btn);

        const node = study.getWorkbench().getNode(nodeId);
        const nodeLabel = node.getLabel();
        const skipNode = slideShow.getPosition(nodeId) === -1;
        if (skipNode) {
          btn.set({
            label: nodeLabel,
            icon: "@FontAwesome5Solid/eye-slash/14"
          });
        } else {
          btn.set({
            label: currentPos+1 + " - " + nodeLabel
          });
          currentPos++;
        }
        btn.nodeId = nodeId;
        btn.skipNode = skipNode;

        this.__addEditNodeMenu(btn, currentPos);

        if (i === nodeIds.length-1) {
          // for now, plus buttons only at the beginning and end
          newServiceBtn = this.__createNewServiceBtn();
          newServiceBtn.leftNodeId = nodeId;
          newServiceBtn.rightNodeId = null;
          this._add(newServiceBtn);

          if (!study.getWorkbench().getNode(nodeId).hasOutputs()) {
            newServiceBtn.exclude();
          }
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

    __addEditNodeMenu: function(btn, currentPos) {
      const menu = new qx.ui.menu.Menu();

      if (btn.skipNode) {
        const showButton = new qx.ui.menu.Button("Show", "@FontAwesome5Solid/eye/14");
        showButton.addListener("execute", () => {
          this.fireDataEvent("showNode", {
            nodeId: btn.nodeId,
            desiredPos: currentPos
          });
        });
        menu.add(showButton);
      } else {
        const hideButton = new qx.ui.menu.Button("Hide", "@FontAwesome5Solid/eye-slash/14");
        hideButton.addListener("execute", () => {
          this.fireDataEvent("hideNode", btn.nodeId);
        });
        menu.add(hideButton);
      }

      const deleteButton = new qx.ui.menu.Button("Delete", "@FontAwesome5Solid/trash/14");
      deleteButton.addListener("execute", () => {
        this.fireDataEvent("removeNode", btn.nodeId);
      });
      menu.add(deleteButton);

      btn.setMenu(menu);
    }
  }
});
