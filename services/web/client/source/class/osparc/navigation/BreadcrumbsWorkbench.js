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

qx.Class.define("osparc.navigation.BreadcrumbsWorkbench", {
  extend: osparc.navigation.BreadcrumbNavigation,

  members: {
    populateButtons: function(nodesIds = []) {
      const btns = [];
      for (let i=0; i<nodesIds.length; i++) {
        const nodeId = nodesIds[i];
        const btn = this.__createBtns(nodeId);
        if (i === nodesIds.length-1) {
          btn.setValue(true);
        }
        btns.push(btn);
      }
      this._buttonsToBreadcrumb(btns, "slash");
    },

    __createBtns: function(nodeId) {
      const btn = this._createNodeBtn(nodeId);
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      if (nodeId === study.getUuid()) {
        study.bind("name", btn, "label");
        study.bind("name", btn, "toolTipText");
      } else {
        const node = study.getWorkbench().getNode(nodeId);
        if (node) {
          node.bind("label", btn, "label");
          node.bind("label", btn, "toolTipText");
        }
      }
      return btn;
    }
  }
});
