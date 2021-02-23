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
          converter: val => (pos+1).toString() + "- " + val
        });
        node.bind("label", btn, "toolTipText");

        const nsUI = new osparc.ui.basic.NodeStatusUI(node);
        const nsUIIcon = nsUI.getChildControl("icon");
        // Hacky, aber schön
        // eslint-disable-next-line no-underscore-dangle
        btn._add(nsUIIcon);
        const nsUILabel = nsUI.getChildControl("label");
        nsUILabel.addListener("changeValue", e => {
          const statusLabel = e.getData();
          if (statusLabel) {
            btn.setToolTipText(`${node.getLabel()} - ${statusLabel}`);
          }
        }, this);
        if (nsUILabel.getValue()) {
          btn.setToolTipText(`${node.getLabel()} - ${nsUILabel.getValue()}`);
        }
      }
      return btn;
    }
  }
});
