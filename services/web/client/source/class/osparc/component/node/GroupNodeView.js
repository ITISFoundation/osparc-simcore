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
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let groupNodeView = new osparc.component.node.GroupNodeView();
 *   groupNodeView.setNode(workbench.getNode1());
 *   groupNodeView.populateLayout();
 *   this.getRoot().add(groupNodeView);
 * </pre>
 */

qx.Class.define("osparc.component.node.GroupNodeView", {
  extend: osparc.component.node.BaseNodeView,

  construct: function() {
    this.base(arguments);
  },

  statics: {
    getSettingsEditorLayout: function(nodes) {
      const settingsEditorLayout = osparc.component.node.BaseNodeView.createSettingsGroupBox("Settings");
      Object.values(nodes).forEach(innerNode => {
        const propsFormEditor = innerNode.getPropsFormEditor();
        if (propsFormEditor && Object.keys(innerNode.getInputs()).length) {
          const innerSettings = osparc.component.node.BaseNodeView.createSettingsGroupBox().set({
            maxWidth: 700
          });
          innerNode.bind("label", innerSettings, "legend");
          innerSettings.add(propsFormEditor);
          settingsEditorLayout.add(innerSettings);
        }
      });
      return settingsEditorLayout;
    },

    isSettingsGroupShowable: function(innerNodes) {
      const innerNodesArray = Object.values(innerNodes);
      for (let i=0; i<innerNodesArray.length; i++) {
        const innerNode = innerNodesArray[i];
        if (osparc.component.node.NodeView.isPropsFormShowable(innerNode)) {
          return true;
        }
      }
      return false;
    }
  },

  members: {
    _addSettings: function() {
      this._settingsLayout.removeAll();

      const innerNodes = this.getNode().getInnerNodes(true);
      Object.values(innerNodes).forEach(innerNode => {
        const propsForm = innerNode.getPropsForm();
        if (propsForm && Object.keys(innerNode.getInputs()).length && propsForm.hasVisibleInputs()) {
          const innerSettings = osparc.component.node.BaseNodeView.createSettingsGroupBox();
          innerNode.bind("label", innerSettings, "legend");
          innerSettings.add(propsForm);
          propsForm.addListener("changeChildVisibility", () => {
            const isSettingsGroupShowable = osparc.component.node.NodeView.isPropsFormShowable(innerNode);
            innerSettings.setVisibility(isSettingsGroupShowable ? "visible" : "excluded");
            this.__checkSettingsVisibility();
          }, this);
          this._settingsLayout.add(innerSettings);
        }
        this.__checkSettingsVisibility();
      });

      this._addToMainView(this._settingsLayout);
    },

    __checkSettingsVisibility: function() {
      const isSettingsGroupShowable = this.isSettingsGroupShowable();
      this._settingsLayout.setVisibility(isSettingsGroupShowable ? "visible" : "excluded");
    },

    isSettingsGroupShowable: function() {
      const innerNodes = this.getNode().getInnerNodes(true);
      return this.self().isSettingsGroupShowable(innerNodes);
    },

    __iFrameChanged: function(innerNode, tabPage) {
      const loadingPage = innerNode.getLoadingPage();
      const iFrame = innerNode.getIFrame();

      tabPage.removeAll();
      const src = iFrame.getSource();
      if (src === null || src === "about:blank") {
        tabPage.add(loadingPage);
      } else {
        tabPage.add(iFrame);
      }
    },

    _addIFrame: function() {
      this._iFrameLayout.removeAll();

      const tabView = new qx.ui.tabview.TabView().set({
        contentPadding: 0
      });
      const innerNodes = this.getNode().getInnerNodes(true);
      Object.values(innerNodes).forEach(innerNode => {
        const loadingPage = innerNode.getLoadingPage();
        const iFrame = innerNode.getIFrame();
        if (loadingPage === null && iFrame === null) {
          return;
        }
        [
          loadingPage,
          iFrame
        ].forEach(widget => {
          if (widget) {
            widget.addListener("maximize", e => {
              this.__maximizeIFrame(true);
            }, this);
            widget.addListener("restore", e => {
              this.__maximizeIFrame(false);
            }, this);
            this.__maximizeIFrame(widget.hasState("maximized"));
          }
        });

        const page = new qx.ui.tabview.Page().set({
          layout: new qx.ui.layout.Grow(),
          showCloseButton: false
        });
        innerNode.bind("label", page, "label");
        tabView.add(page);

        this.__iFrameChanged(innerNode, page);

        iFrame.addListener("load", () => {
          this.__iFrameChanged(innerNode, page);
        });
      });

      if (tabView.getChildren()) {
        this._iFrameLayout.add(tabView, {
          flex: 1
        });

        this._addToMainView(this._iFrameLayout, {
          flex: 1
        });
      }
    },

    __maximizeIFrame: function(maximize) {
      const othersStatus = maximize ? "excluded" : "visible";
      const isSettingsGroupShowable = this.isSettingsGroupShowable();
      const othersStatus2 = isSettingsGroupShowable && !maximize ? "visible" : "excluded";
      this._settingsLayout.setVisibility(othersStatus2);
      this.__header.setVisibility(othersStatus);
    },

    _openEditAccessLevel: function() {
      const settingsEditorLayout = this.self().getSettingsEditorLayout(this.getNode().getInnerNodes());
      const title = this.getNode().getLabel();
      osparc.ui.window.Window.popUpInWindow(settingsEditorLayout, title, 800, 600).set({
        autoDestroy: false
      });
    },

    _applyNode: function(node) {
      if (!node.isContainer()) {
        console.error("Only group nodes are supported");
      }
      this.base(arguments, node);
    }
  }
});
