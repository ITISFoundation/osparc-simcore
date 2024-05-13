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
 *   let nodeView = new osparc.node.NodeView();
 *   nodeView.setNode(workbench.getNode1());
 *   this.getRoot().add(nodeView);
 * </pre>
 */

qx.Class.define("osparc.node.NodeView", {
  extend: osparc.node.BaseNodeView,

  statics: {
    LOGGER_HEIGHT: 28,

    isPropsFormShowable: function(node) {
      if (node && ("getPropsForm" in node) && node.getPropsForm()) {
        return node.getPropsForm().hasVisibleInputs();
      }
      return false;
    }
  },

  members: {
    __loggerPanel: null,

    // overridden
    _addSettings: function() {
      this._settingsLayout.removeAll();

      const node = this.getNode();
      const propsForm = node.getPropsForm();
      if (propsForm && node.hasInputs()) {
        propsForm.addListener("changeChildVisibility", () => {
          this.__checkSettingsVisibility();
        }, this);
        this._settingsLayout.add(propsForm);
      }
      this.__checkSettingsVisibility();

      this._mainView.add(this._settingsLayout);
    },

    // overridden
    _addIFrame: function() {
      this._iFrameLayout.removeAll();

      const loadingPage = this.getNode().getLoadingPage();
      const iFrame = this.getNode().getIFrame();
      if (loadingPage && iFrame) {
        this.__iFrameChanged();
        iFrame.addListener("load", () => this.__iFrameChanged());
      } else {
        // This will keep what comes after at the bottom
        this._iFrameLayout.add(new qx.ui.core.Spacer(), {
          flex: 1
        });
      }

      this._mainView.add(this._iFrameLayout, {
        flex: 1
      });
    },

    // overridden
    _addOutputs: function() {
      this._outputsLayout.removeAll();

      const nodeOutputs = new osparc.widget.NodeOutputs(this.getNode(), this.getNode().getMetaData().outputs);
      this._mainView.bind("backgroundColor", nodeOutputs, "backgroundColor");
      this._outputsLayout.add(nodeOutputs);

      this._outputsBtn.set({
        value: false,
        enabled: this.getNode().hasOutputs() > 0
      });
    },

    // overridden
    _addLogger: function() {
      const loggerView = this.getNode().getLogger();
      loggerView.getChildControl("pin-node").exclude();
      const loggerPanel = this.__loggerPanel = new osparc.desktop.PanelView(this.tr("Logger"), loggerView).set({
        padding: 3,
        minHeight: this.self().LOGGER_HEIGHT-1,
        collapsed: true
      });
      loggerPanel.bind("collapsed", loggerPanel, "maxHeight", {
        converter: collapsed => collapsed ? this.self().LOGGER_HEIGHT : null
      });
      this.add(loggerPanel, 0);
    },

    getLoggerPanel: function() {
      return this.__loggerPanel;
    },

    // overridden
    _openEditAccessLevel: function() {
      const settingsEditorLayout = osparc.node.BaseNodeView.createSettingsGroupBox(this.tr("Settings"));
      const propsFormEditor = this.getNode().getPropsFormEditor();
      settingsEditorLayout.add(propsFormEditor);
      const title = this.getNode().getLabel();
      osparc.ui.window.Window.popUpInWindow(settingsEditorLayout, title, 800, 600).set({
        autoDestroy: false
      });
    },

    // overridden
    _applyNode: function(node) {
      this.base(arguments, node);
    },

    __checkSettingsVisibility: function() {
      const isSettingsGroupShowable = this.isSettingsGroupShowable();
      this._settingsLayout.setVisibility(isSettingsGroupShowable ? "visible" : "excluded");
    },

    isSettingsGroupShowable: function() {
      const node = this.getNode();
      return this.self().isPropsFormShowable(node);
    },

    __iFrameChanged: function() {
      this._iFrameLayout.removeAll();

      const loadingPage = this.getNode().getLoadingPage();
      const iFrame = this.getNode().getIFrame();
      const src = iFrame.getSource();
      const iFrameView = (src === null || src === "about:blank") ? loadingPage : iFrame;
      this._iFrameLayout.add(iFrameView, {
        flex: 1
      });
    }
  }
});
