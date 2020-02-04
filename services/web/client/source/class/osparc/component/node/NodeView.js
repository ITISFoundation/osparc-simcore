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
    _addSettings: function() {
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

    _addIFrame: function() {
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

    _openEditAccessLevel: function() {
      const win = new qx.ui.window.Window(this.getNode().getLabel()).set({
        layout: new qx.ui.layout.Grow(),
        contentPadding: 10,
        showMinimize: false,
        resizable: true,
        modal: true,
        height: 600,
        width: 800
      });

      const settingsEditorLayout = osparc.component.node.BaseNodeView.createSettingsGroupBox(this.tr("Settings")).set({
        maxWidth: 800
      });
      settingsEditorLayout.add(this.getNode().getPropsWidgetEditor());

      win.add(settingsEditorLayout);
      win.center();
      win.open();
    },

    _applyNode: function(node) {
      if (node.isContainer()) {
        console.error("Only non-group nodes are supported");
      }
    }
  }
});
