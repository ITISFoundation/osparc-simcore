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

  events: {
    "nodeSelectionRequested": "qx.event.type.Data"
  },

  members: {
    populateButtons: function(nodesIds = []) {
      const btns = [];
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const slideshow = study.getUi().getSlideshow();
      if (nodesIds.length) {
        nodesIds.forEach(nodeId => {
          if (slideshow.getPosition(nodeId) === -1) {
            return;
          }
          const btn = this.__createBtn(nodeId);
          btns.push(btn);
        });
        this.__buttonsToBreadcrumb(btns, "separator");
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

    __buttonsToBreadcrumb: function(btns, shape = "separator") {
      this._removeAll();
      for (let i=0; i<btns.length; i++) {
        const thisBtn = btns[i];
        let nextBtn = null;
        if (i+1<btns.length) {
          nextBtn = btns[i+1];
        }

        this._add(thisBtn);

        const breadcrumbSplitter = new osparc.navigation.BreadcrumbSplitter(16, 32).set({
          shape,
          marginLeft: -1,
          marginRight: -1
        });
        const addLeftRightWidgets = (leftBtn, rightBtn) => {
          if (shape === "separator" && (!leftBtn || !rightBtn)) {
            return;
          }
          breadcrumbSplitter.setLeftWidget(leftBtn);
          if (rightBtn) {
            breadcrumbSplitter.setRightWidget(rightBtn);
          }
        };
        if (breadcrumbSplitter.getReady()) {
          addLeftRightWidgets(thisBtn, nextBtn);
        } else {
          breadcrumbSplitter.addListenerOnce("SvgWidgetReady", () => {
            addLeftRightWidgets(thisBtn, nextBtn);
          }, this);
        }
        this._add(breadcrumbSplitter);
      }
    },

    __createBtn: function(nodeId) {
      const btn = this.__createNodeBtn(nodeId);
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
      const btn = new qx.ui.form.Button().set({
        ...osparc.navigation.NavigationBar.BUTTON_OPTIONS,
        maxWidth: 200
      });
      osparc.utils.Utils.setIdToWidget(btn, "appModeButton_"+nodeId);
      btn.addListener("execute", () => this.fireDataEvent("nodeSelectionRequested", nodeId));

      const colorManager = qx.theme.manager.Color.getInstance();
      const updateStyle = () => {
        osparc.utils.Utils.addBorder(btn, 1, colorManager.resolve("text"));
      };
      colorManager.addListener("changeTheme", () => updateStyle(btn), this);
      updateStyle(btn);

      const updateCurrentNodeId = currentNodeId => {
        if (nodeId === currentNodeId) {
          btn.setAppearance("strong-button");
        } else {
          btn.resetAppearance();
        }
        btn.setFont("text-14");
      };
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      updateCurrentNodeId(study.getUi().getCurrentNodeId());
      study.getUi().addListener("changeCurrentNodeId", e => updateCurrentNodeId(e.getData()));

      return btn;
    }
  }
});
