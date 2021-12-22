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

qx.Class.define("osparc.navigation.BreadcrumbsSlideshow", {
  extend: osparc.navigation.BreadcrumbNavigation,

  members: {
    populateButtons: function(nodesIds = []) {
      const btns = [];
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const currentNodeId = study.getUi().getCurrentNodeId();
      if (nodesIds.length) {
        nodesIds.forEach(nodeId => {
          const btn = this.__createBtn(nodeId);
          if (nodeId === currentNodeId) {
            btn.setValue(true);
          }
          btns.push(btn);
        });
        this._buttonsToBreadcrumb(btns, "separator");
      } else {
        this._removeAll();
        const label = new qx.ui.basic.Label();
        if (study.isPipelineEmtpy()) {
          label.setValue(this.tr("Pipeline is empty"));
        } else {
          label.setValue(this.tr("There are no visible nodes, enable some by editing the slideshow"));
        }
        this._add(label);
      }
    },

    __setButtonStyle: function(btn) {
      btn.getContentElement().setStyles({
        "border-radius": "6px",
        "box-shadow": "none"
      });

      const updateStyle = button => {
        const colorManager = qx.theme.manager.Color.getInstance();
        if (button.getEnabled() === false) {
          // disabled
          button.set({
            textColor: "text-disabled",
            backgroundColor: "transparent"
          });
          button.getContentElement().setStyles({
            "border": "1px solid " + colorManager.resolve("text")
          });
        } else if (button.getValue() === false) {
          // enabled but not current
          button.set({
            textColor: "text",
            backgroundColor: "transparent"
          });
          button.getContentElement().setStyles({
            "border": "1px solid " + colorManager.resolve("text")
          });
        } else {
          // current
          button.set({
            textColor: "text",
            backgroundColor: "background-main-lighter+"
          });
          button.getContentElement().setStyles({
            "border": "0px"
          });
        }
      };

      updateStyle(btn);
      btn.addListener("changeValue", () => updateStyle(btn), this);
      btn.addListener("changeEnabled", () => updateStyle(btn), this);
      const colorManager = qx.theme.manager.Color.getInstance();
      colorManager.addListener("changeTheme", () => updateStyle(btn), this);
    },

    __createBtn: function(nodeId) {
      const btn = this._createNodeBtn(nodeId);
      this.__setButtonStyle(btn);
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const slideshow = study.getUi().getSlideshow().getData();
      const node = study.getWorkbench().getNode(nodeId);
      if (node && nodeId in slideshow) {
        const pos = slideshow[nodeId].position;
        node.bind("label", btn, "label", {
          converter: val => `${pos+1}: ${val}`
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
              osparc.ui.basic.NodeStatusUI.addClass(elem, "rotate");
            } else {
              osparc.ui.basic.NodeStatusUI.removeClass(elem, "rotate");
            }
          }
        });
        node.getStatus().bind(check, statusIcon, "textColor", {
          converter: output => osparc.utils.StatusUI.getColor(output)
        }, this);
        // eslint-disable-next-line no-underscore-dangle
        btn._addAt(statusIcon, 0);

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
