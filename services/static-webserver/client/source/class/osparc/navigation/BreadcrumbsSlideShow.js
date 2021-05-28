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
        node.getStatus().bind("dependencies", btn.getChildControl("label"), "font", {
          converter: dependencies => (dependencies && dependencies.length) ? "text-14" : "title-14"
        });
        node.getStatus().bind("dependencies", btn.getChildControl("label"), "textColor", {
          converter: dependencies => (dependencies && dependencies.length) ? "material-button-text-disabled" : "material-button-text"
        });

        const statusIcon = new qx.ui.basic.Image();
        node.getStatus().bind("output", statusIcon, "source", {
          converter: output => {
            switch (output) {
              case "up-to-date":
                return osparc.utils.StatusUI.getIconSource("up-to-date");
              case "out-of-date":
                return osparc.utils.StatusUI.getIconSource("modified");
              case "busy":
                return osparc.utils.StatusUI.getIconSource("running");
              case "not-available":
              default:
                return osparc.utils.StatusUI.getIconSource();
            }
          },
          onUpdate: (source, target) => (source.getOutput() === "busy") ? target.getContentElement().addClass("rotate") : target.getContentElement().removeClass("rotate")
        });
        node.getStatus().bind("output", statusIcon, "textColor", {
          converter: output => {
            switch (output) {
              case "up-to-date":
                return osparc.utils.StatusUI.getColor("ready");
              case "out-of-date":
              case "busy":
                return osparc.utils.StatusUI.getColor("modified");
              case "not-available":
              default:
                return osparc.utils.StatusUI.getColor();
            }
          }
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
