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
      const slideshow = study.getUi().getSlideshow();
      if (nodesIds.length) {
        nodesIds.forEach(nodeId => {
          if (slideshow.getPosition(nodeId) === -1) {
            return;
          }
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
        if (study.isPipelineEmpty()) {
          label.setValue(this.tr("Pipeline is empty"));
        } else {
          label.setValue(this.tr("There are no visible nodes, enable some by editing the App Mode"));
        }
        this._add(label);
      }
    },

    __setButtonStyle: function(btn) {
      const colorManager = qx.theme.manager.Color.getInstance();
      const updateStyle = button => {
        osparc.utils.Utils.addBorder(button, 1, colorManager.resolve("text"));
      };
      colorManager.addListener("changeTheme", () => updateStyle(btn), this);
      updateStyle(btn);

      btn.addListener("changeValue", e => {
        if (e.getData()) {
          btn.setFont("text-14");
          btn.setAppearance("strong-button");
        } else {
          btn.resetFont();
          btn.resetAppearance();
        }
      });
    },

    __createBtn: function(nodeId) {
      const btn = this.__createNodeBtn(nodeId);
      this.__setButtonStyle(btn);
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const slideshow = study.getUi().getSlideshow().getData();
      const node = study.getWorkbench().getNode(nodeId);
      if (node && nodeId in slideshow) {
        const pos = slideshow[nodeId].position;
        osparc.utils.Utils.setIdToWidget(btn, "AppMode_StepBtn_"+(pos+1));
        node.bind("label", btn, "label", {
          converter: val => `${pos+1}: ${val}`
        });
        node.getStatus().bind("dependencies", btn.getChildControl("label"), "textColor", {
          converter: dependencies => (dependencies && dependencies.length) ? "material-button-text-disabled" : "material-button-text"
        });

        const statusIcon = new qx.ui.basic.Image();
        if (node.isFilePicker()) {
          osparc.utils.StatusUI.setupFilePickerIcon(node, statusIcon);
        } else {
          const check = node.isDynamic() ? "interactive" : "output";
          node.getStatus().bind(check, statusIcon, "source", {
            converter: output => osparc.utils.StatusUI.getIconSource(output),
            onUpdate: (_, target) => osparc.utils.StatusUI.updateCircleAnimation(target)
          });
          node.getStatus().bind(check, statusIcon, "textColor", {
            converter: output => osparc.utils.StatusUI.getColor(output)
          }, this);
        }
        // eslint-disable-next-line no-underscore-dangle
        btn._addAt(statusIcon, 0);

        const statusUI = new osparc.ui.basic.NodeStatusUI(node);
        const statusLabel = statusUI.getChildControl("label");
        statusLabel.bind("value", btn, "toolTipText", {
          converter: status => `${node.getLabel()} - ${status}`
        });
      }
      return btn;
    },

    __createNodeBtn: function(nodeId) {
      const btn = new qx.ui.form.ToggleButton().set({
        ...osparc.navigation.NavigationBar.BUTTON_OPTIONS,
        maxWidth: 200
      });
      osparc.utils.Utils.setIdToWidget(btn, "appModeButton_"+nodeId);
      btn.addListener("execute", e => {
        if (btn.getValue()) {
          // Unselected button clicked
          this.fireDataEvent("nodeSelected", nodeId);
        } else {
          // Selected button clicked. Don't allo
          btn.setValue(true);
        }
      }, this);
      return btn;
    }
  }
});
