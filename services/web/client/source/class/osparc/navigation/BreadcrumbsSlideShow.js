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

  members: {
    populateButtons: function(nodesIds = []) {
      const btns = [];
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const currentNodeId = study.getUi().getCurrentNodeId();
      for (let i=0; i<nodesIds.length; i++) {
        const nodeId = nodesIds[i];
        const btn = this.__createBtns(nodeId);
        if (nodeId === currentNodeId) {
          btn.setValue(true);
        }
        btns.push(btn);
      }
      this._buttonsToBreadcrumb(btns, "arrow");
    },

    __createBtns: function(nodeId) {
      const btn = this._createNodeBtn(nodeId);
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const slideShow = study.getUi().getSlideshow();
      const node = study.getWorkbench().getNode(nodeId);
      if (node && nodeId in slideShow) {
        const pos = slideShow[nodeId].position;
        node.bind("label", btn, "label", {
          converter: val => `${pos+1}- ${val}`
        });
        node.getStatus().bind("dependencies", btn, "enabled", {
          converter: dependencies => {
            if (dependencies !== null) {
              const waiting = Boolean(dependencies.length);
              return !waiting;
            }
            return true;
          }
        });
        node.getStatus().bind("modified", btn, "label", {
          converter: modified => {
            const label = btn.getLabel();
            const lastCharacter = label.slice(-1);
            if (modified === true && lastCharacter !== "*") {
              return label + "*"; // add star suffix
            } else if (modified === false && lastCharacter === "*") {
              return label.slice(0, -1); // remove star suffix
            }
            return label;
          }
        });
        node.bind("label", btn, "toolTipText");

        const statusUI = new osparc.ui.basic.NodeStatusUI(node);
        const statusIcon = statusUI.getChildControl("icon");
        // eslint-disable-next-line no-underscore-dangle
        btn._add(statusIcon);
        const statusLabel = statusUI.getChildControl("label");
        statusLabel.addListener("changeValue", e => {
          const newStatusLabel = e.getData();
          if (newStatusLabel) {
            btn.setToolTipText(`${node.getLabel()} - ${newStatusLabel}`);
          }
        }, this);
        if (statusLabel.getValue()) {
          btn.setToolTipText(`${node.getLabel()} - ${statusLabel.getValue()}`);
        }
      }
      return btn;
    }
  }
});
