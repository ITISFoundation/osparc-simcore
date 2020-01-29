/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget that displays the main view of a node.
 * - On the left side shows the default inputs if any and also what the input nodes offer
 * - In the center the content of the node: settings, mapper, iframe...
 *
 * When a node is set the layout is built
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let nodeView = new osparc.component.node.NodeView();
 *   nodeView.setNode(workbench.getNode1());
 *   nodeView.populateLayout();
 *   this.getRoot().add(nodeView);
 * </pre>
 */

qx.Class.define("osparc.component.node.NodeView", {
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

      const node = this.getNode();
      const propsWidget = node.getPropsWidget();
      if (propsWidget && Object.keys(node.getInputs()).length) {
        this._settingsLayout.add(propsWidget);
      }
      const mapper = node.getInputsMapper();
      if (mapper) {
        this._mapperLayout.add(mapper, {
          flex: 1
        });
      }

      this._addToMainView(this._settingsLayout);
      this._addToMainView(this._mapperLayout, {
        flex: 1
      });
    },

    __addIFrame: function() {
      this._iFrameLayout.removeAll();

      const iFrame = this.getNode().getIFrame();
      if (iFrame) {
        iFrame.addListener("maximize", e => {
          this._maximizeIFrame(true);
        }, this);
        iFrame.addListener("restore", e => {
          this._maximizeIFrame(false);
        }, this);
        this._maximizeIFrame(iFrame.hasState("maximized"));
        this._iFrameLayout.add(iFrame, {
          flex: 1
        });
      }

      this._addToMainView(this._iFrameLayout, {
        flex: 1
      });
    },

    _applyNode: function(node) {
      if (node.isContainer()) {
        console.error("Only non-group nodes are supported");
      }
    }
  }
});
