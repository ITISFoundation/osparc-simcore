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

  members: {
    populateLayout: function() {
      this.getNode().bind("label", this._title, "value");
      this._addInputPortsUIs();
      this.__addSettings();
      this.__addIFrame();
      this._addButtons();
    },

    __addSettings: function() {
      this._settingsLayout.removeAll();
      this._mapperLayout.removeAll();

      const innerNodes = this.getNode().getInnerNodes(true);
      Object.values(innerNodes).forEach(innerNode => {
        const innerSettings = osparc.component.node.BaseNodeView.createSettingsGroupBox();
        innerNode.bind("label", innerSettings, "legend");
        const propsWidget = innerNode.getPropsWidget();
        if (propsWidget && Object.keys(innerNode.getInputs()).length) {
          innerSettings.add(propsWidget);
          this._settingsLayout.add(innerSettings);
        }
        const mapper = innerNode.getInputsMapper();
        if (mapper) {
          this._mapperLayout.add(mapper, {
            flex: 1
          });
        }
      });

      this._addToMainView(this._settingsLayout);
      this._addToMainView(this._mapperLayout, {
        flex: 1
      });
    },

    __addIFrame: function() {
      this._iFrameLayout.removeAll();

      const tabView = new qx.ui.tabview.TabView();
      const innerNodes = this.getNode().getInnerNodes(true);
      Object.values(innerNodes).forEach(innerNode => {
        const iFrame = innerNode.getIFrame();
        if (iFrame) {
          const page = new qx.ui.tabview.Page().set({
            layout: new qx.ui.layout.Canvas(),
            showCloseButton: false
          });
          innerNode.bind("label", page, "label");
          page.add(iFrame, {
            left: 0,
            top: 0,
            right: 0,
            bottom: 0
          });
          tabView.add(page);

          iFrame.addListener("maximize", e => {
            this._maximizeIFrame(true);
          }, this);
          iFrame.addListener("restore", e => {
            this._maximizeIFrame(false);
          }, this);
          this._maximizeIFrame(iFrame.hasState("maximized"));
          this._iFrameLayout.add(tabView, {
            flex: 1
          });
        }
      });

      this._addToMainView(this._iFrameLayout, {
        flex: 1
      });
    },

    _applyNode: function(node) {
      if (!node.isContainer()) {
        console.error("Only group nodes are supported");
      }
    }
  }
});
