/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 *
 */

qx.Class.define("osparc.component.widget.BreadcrumbNavigation", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(0).set({
      alignY: "middle"
    }));
  },

  events: {
    "nodeSelected": "qx.event.type.Data"
  },

  statics: {
    BUTTON_OPTIONS: {
      font: "text-14",
      allowGrowY: false,
      minWidth: 32,
      minHeight: 32
    }
  },

  members: {
    populateButtons: function(nodesIds = [], shape = "slash") {
      const btns = [];
      if (shape === "slash") {
        for (let i=0; i<nodesIds.length; i++) {
          const nodeId = nodesIds[i];
          const btn = this.__createNodePathBtn(nodeId);
          if (i === nodesIds.length-1) {
            btn.setValue(true);
          }
          btns.push(btn);
        }
      } else if (shape === "arrow") {
        const study = osparc.store.Store.getInstance().getCurrentStudy();
        const currentNodeId = study.getUi().getCurrentNodeId();
        for (let i=0; i<nodesIds.length; i++) {
          const nodeId = nodesIds[i];
          const btn = this.__createNodeSlideBtn(nodeId);
          if (nodeId === currentNodeId) {
            btn.setValue(true);
          }
          btns.push(btn);
        }
      }
      this.__buttonsToBreadcrumb(btns, shape);
    },

    __createNodeBtn: function(nodeId) {
      const btn = new qx.ui.form.ToggleButton().set({
        ...this.self().BUTTON_OPTIONS,
        maxWidth: 200
      });
      btn.addListener("execute", () => {
        this.fireDataEvent("nodeSelected", nodeId);
      }, this);
      return btn;
    },

    __createNodePathBtn: function(nodeId) {
      const btn = this.__createNodeBtn(nodeId);
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
    },

    __createNodeSlideBtn: function(nodeId) {
      const btn = this.__createNodeBtn(nodeId);
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const slideShow = study.getUi().getSlideshow();
      const node = study.getWorkbench().getNode(nodeId);
      if (node && nodeId in slideShow) {
        const pos = slideShow[nodeId].position;
        node.bind("label", btn, "label", {
          converter: val => (pos+1).toString() + "- " + val
        });
        node.bind("label", btn, "toolTipText");
      }
      return btn;
    },

    __buttonsToBreadcrumb: function(btns, shape = "slash") {
      this._removeAll();
      for (let i=0; i<btns.length; i++) {
        const thisBtn = btns[i];
        let nextBtn = null;
        if (i+1<btns.length) {
          nextBtn = btns[i+1];
        }

        this._add(thisBtn);

        const breadcrumbSplitter = new osparc.component.widget.BreadcrumbSplitter(16, 32).set({
          shape,
          marginLeft: -1,
          marginRight: -1
        });
        if (breadcrumbSplitter.getReady()) {
          breadcrumbSplitter.setLeftWidget(thisBtn);
          if (nextBtn) {
            breadcrumbSplitter.setRightWidget(nextBtn);
          }
        } else {
          breadcrumbSplitter.addListenerOnce("SvgWidgetReady", () => {
            breadcrumbSplitter.setLeftWidget(thisBtn);
            if (nextBtn) {
              breadcrumbSplitter.setRightWidget(nextBtn);
            }
          }, this);
        }
        this._add(breadcrumbSplitter);
      }
    }
  }
});
