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
        propsWidget.addListener("changeChildVisibility", () => {
          this.__checkSettingsVisibility();
        }, this);
        this._settingsLayout.add(propsWidget);
      }
      this.__checkSettingsVisibility();
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

    __checkSettingsVisibility: function() {
      const isSettingsGroupShowable = this.isSettingsGroupShowable();
      this._settingsLayout.setVisibility(isSettingsGroupShowable ? "visible" : "excluded");
    },

    isSettingsGroupShowable: function() {
      const node = this.getNode();
      if (node && ("getPropsWidget" in node) && node.getPropsWidget()) {
        return node.getPropsWidget().hasVisibleInputs();
      }
      return false;
    },

    __iFrameChanged: function() {
      this._iFrameLayout.removeAll();

      const loadingPage = this.getNode().getLoadingPage();
      const iFrame = this.getNode().getIFrame();
      const src = iFrame.getSource();
      if (src === null || src === "about:blank") {
        this._iFrameLayout.add(loadingPage, {
          flex: 1
        });
      } else {
        this._iFrameLayout.add(iFrame, {
          flex: 1
        });
      }
    },

    _addIFrame: function() {
      this._iFrameLayout.removeAll();

      const loadingPage = this.getNode().getLoadingPage();
      const iFrame = this.getNode().getIFrame();
      if (loadingPage === null && iFrame === null) {
        return;
      }
      [
        loadingPage,
        iFrame
      ].forEach(widget => {
        if (widget) {
          widget.addListener("maximize", e => {
            this._maximizeIFrame(true);
          }, this);
          widget.addListener("restore", e => {
            this._maximizeIFrame(false);
          }, this);
          this._maximizeIFrame(widget.hasState("maximized"));
        }
      });
      this.__iFrameChanged();

      iFrame.addListener("load", () => {
        this.__iFrameChanged();
      });

      this._addToMainView(this._iFrameLayout, {
        flex: 1
      });
    },

    _openEditAccessLevel: function() {
      const settingsEditorLayout = osparc.component.node.BaseNodeView.createSettingsGroupBox(this.tr("Settings"));
      settingsEditorLayout.add(this.getNode().getPropsWidgetEditor());

      const win = osparc.component.node.BaseNodeView.createWindow(this.getNode().getLabel());
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
