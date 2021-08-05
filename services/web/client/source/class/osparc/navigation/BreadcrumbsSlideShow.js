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
      nodesIds.forEach(nodeId => {
        const btn = this.__createBtn(nodeId);
        if (nodeId === currentNodeId) {
          btn.setValue(true);
        }
        btns.push(btn);
      });
      this._buttonsToBreadcrumb(btns, "arrow");
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
    }
  }
});
