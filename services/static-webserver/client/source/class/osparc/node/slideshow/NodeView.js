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
 *   let nodeView = new osparc.node.slideshow.NodeView();
 *   nodeView.setNode(workbench.getNode1());
 *   this.getRoot().add(nodeView);
 * </pre>
 */

qx.Class.define("osparc.node.slideshow.NodeView", {
  extend: osparc.node.slideshow.BaseNodeView,

  statics: {
    LOGGER_HEIGHT: 28,
  },

  members: {
    __loggerPanel: null,

    // overridden
    _addSettings: function() {
      this._settingsLayout.removeAll();

      const node = this.getNode();
      if (
        node.isComputational() &&
        node.hasInputs() &&
        "getPropsForm" in node &&
        node.getPropsForm() &&
        node.getPropsForm().hasVisibleInputs()
      ) {
        this._settingsLayout.add(node.getPropsForm());

        // lock the inputs if the node is locked
        node.getStatus().getLockState().bind("locked", node.getPropsForm(), "enabled", {
          converter: locked => !locked
        });
      }

      const showSettings = node.isComputational();
      this._settingsLayout.setVisibility(showSettings ? "visible" : "excluded");

      this._mainView.add(this._settingsLayout);
    },

    // overridden
    _addIFrame: function() {
      this._iFrameLayout.removeAll();

      const loadingPage = this.getNode().getLoadingPage();
      const iFrame = this.getNode().getIFrame();
      if (loadingPage && iFrame) {
        const node = this.getNode();
        node.getIframeHandler().addListener("iframeStateChanged", () => this.__iFrameStateChanged(), this);
        iFrame.addListener("load", () => this.__iFrameStateChanged());
        this.__iFrameStateChanged();
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

      const node = this.getNode();
      const outputsForm = node.getOutputsForm();
      if (node.hasOutputs() && outputsForm) {
        this._mainView.bind("backgroundColor", outputsForm, "backgroundColor");
        this._outputsLayout.add(outputsForm);
      }

      this.getOutputsButton().set({
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
    _applyNode: function(node) {
      this.base(arguments, node);
    },

    __iFrameStateChanged: function() {
      this._iFrameLayout.removeAll();

      const node = this.getNode();
      if (node && node.getIFrame()) {
        const loadingPage = node.getLoadingPage();
        const iFrame = node.getIFrame();
        const src = iFrame.getSource();
        const iFrameView = (src === null || src === "about:blank") ? loadingPage : iFrame;
        this._iFrameLayout.add(iFrameView, {
          flex: 1
        });
      }
    }
  }
});
