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

qx.Class.define("osparc.navigation.BreadcrumbsSlideShow", {
  extend: osparc.navigation.BreadcrumbNavigation,

  construct: function() {
    this.base(arguments);

    this.addListener("changeEditMode", () => {
      if (this.getEditMode()) {
        this.__buildEditMode();
      } else {
        this.populateButtons(this.__nodesIds);
      }
    }, this);
  },

  properties: {
    editMode: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeEditMode"
    }
  },

  members: {
    __nodesIds: null,

    populateButtons: function(nodesIds = []) {
      this.__nodesIds = nodesIds;
      const btns = [];
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const currentNodeId = study.getUi().getCurrentNodeId();
      nodesIds.forEach(nodeId => {
        const btn = this.__createBtn(nodeId);
        if (nodeId === currentNodeId) {
          btn.setValue(true);
        }
        btns.push(btn);
      });
      if (this.getEditMode()) {
        this._buttonsToBreadcrumb(btns, "plusBtn");
      } else {
        this._buttonsToBreadcrumb(btns, "arrow");
      }
    },

    __createBtn: function(nodeId) {
      const btn = this._createNodeBtn(nodeId);
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const slideShow = study.getUi().getSlideshow();
      const node = study.getWorkbench().getNode(nodeId);
      if (node && nodeId in slideShow) {
        const pos = slideShow[nodeId].position;
        node.bind("label", btn, "label", {
          converter: val => `${pos+1}- ${val}`
        });
        node.getStatus().bind("dependencies", btn.getChildControl("label"), "font", {
          converter: dependencies => (dependencies && dependencies.length) ? "text-14" : "title-14"
        });
        node.getStatus().bind("dependencies", btn.getChildControl("label"), "textColor", {
          converter: dependencies => (dependencies && dependencies.length) ? "material-button-text-disabled" : "material-button-text"
        });

        const statusIcon = new qx.ui.basic.Image();
        const check = node.isDynamic() ? "interactive" : "output";
        node.getStatus().bind(check, statusIcon, "source", {
          converter: output => osparc.utils.StatusUI.getIconSource(output),
          onUpdate: (source, target) => {
            const elem = target.getContentElement();
            const state = source.get(check);
            if (["busy", "starting", "pulling", "pending", "connecting"].includes(state)) {
              elem.addClass("rotate");
            } else {
              elem.removeClass("rotate");
            }
          }
        });
        node.getStatus().bind(check, statusIcon, "textColor", {
          converter: output => osparc.utils.StatusUI.getColor(output)
        }, this);
        // eslint-disable-next-line no-underscore-dangle
        btn._add(statusIcon);

        const statusUI = new osparc.ui.basic.NodeStatusUI(node);
        const statusLabel = statusUI.getChildControl("label");
        statusLabel.bind("value", btn, "toolTipText", {
          converter: status => `${node.getLabel()} - ${status}`
        });
      }
      return btn;
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
    },

    __buildEditMode: function() {
      this._removeAll();

      let newServiceBtn = this.__createNewServiceBtn();
      this._add(newServiceBtn);

      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const slideShow = study.getUi().getSlideshow();

      this.__nodesIds.forEach(nodeId => {
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
    }
  }
});
