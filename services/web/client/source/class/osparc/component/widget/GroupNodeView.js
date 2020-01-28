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
 *   let groupNodeView = new osparc.component.widget.GroupNodeView();
 *   groupNodeView.setNode(workbench.getNode1());
 *   groupNodeView.populateLayout();
 *   this.getRoot().add(groupNodeView);
 * </pre>
 */

qx.Class.define("osparc.component.widget.GroupNodeView", {
  extend: qx.ui.splitpane.Pane,

  construct: function() {
    this.base(arguments);

    this.__buildLayout();

    this.__attachEventHandlers();
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
      apply: "_applyNode"
    }
  },

  members: {
    __title: null,
    __toolbar: null,
    __mainView: null,
    __settingsLayout: null,
    __mapperLayout: null,
    __iFrameLayout: null,
    __buttonContainer: null,

    __buildMainView: function() {
      const mainView = this.__mainView = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
      this.add(mainView, 1);

      this.__settingsLayout = osparc.component.widget.NodeView.createSettingsGroupBox(this.tr("Settings"));
      this.__mapperLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
      this.__iFrameLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox());

      mainView.add(this.__initToolbar());
    },

    __buildLayout: function() {
      this.__buildMainView();
    },

    __initToolbar: function() {
      const toolbar = this.__toolbar = new qx.ui.toolbar.ToolBar();
      const titlePart = new qx.ui.toolbar.Part();
      const infoPart = new qx.ui.toolbar.Part();
      this.__buttonContainer = new qx.ui.toolbar.Part();
      toolbar.add(titlePart);
      toolbar.add(infoPart);
      toolbar.addSpacer();

      const title = this.__title = new osparc.ui.form.EditLabel().set({
        labelFont: "title-18",
        inputFont: "text-18"
      });
      titlePart.add(title);

      const infoBtn = new qx.ui.toolbar.Button(this.tr("Info"), "@FontAwesome5Solid/info-circle/14");
      infoPart.add(infoBtn);

      infoBtn.addListener("execute", () => this.__openServiceInfo(), this);

      title.addListener("editValue", evt => {
        if (evt.getData() !== this.__title.getValue()) {
          const node = this.getNode();
          if (node) {
            node.renameNode(evt.getData());
          }
          const study = osparc.store.Store.getInstance().getCurrentStudy();
          qx.event.message.Bus.getInstance().dispatchByName(
            "updateStudy",
            study.serializeStudy()
          );
        }
      }, this);

      return toolbar;
    },

    populateLayout: function() {
      this.getNode().bind("label", this.__title, "value");
      this.__addSettings();
      this.__addMapper();
      this.__addIFrame();
      this.__addButtons();
    },

    __addToMainView: function(view, options = {}) {
      if (view.hasChildren()) {
        this.__mainView.add(view, options);
      } else if (qx.ui.core.Widget.contains(this.__mainView, view)) {
        this.__mainView.remove(view);
      }
    },

    __addSettings: function() {
      this.__settingsLayout.removeAll();

      const innerNodes = this.getNode().getInnerNodes(true);
      Object.values(innerNodes).forEach(innerNode => {
        const innerSettings = osparc.component.widget.NodeView.createSettingsGroupBox();
        innerNode.bind("label", innerSettings, "legend");
        const propsWidget = innerNode.getPropsWidget();
        if (propsWidget && Object.keys(innerNode.getInputs()).length) {
          innerSettings.add(propsWidget);
          this.__settingsLayout.add(innerSettings);
        }
      });

      this.__addToMainView(this.__settingsLayout);
    },

    __addMapper: function() {
      this.__mapperLayout.removeAll();

      const innerNodes = this.getNode().getInnerNodes(true);
      Object.values(innerNodes).forEach(innerNode => {
        const mapper = innerNode.getInputsMapper();
        if (mapper) {
          this.__mapperLayout.add(mapper, {
            flex: 1
          });
        }
      });

      this.__addToMainView(this.__mapperLayout, {
        flex: 1
      });
    },

    __addIFrame: function() {
      this.__iFrameLayout.removeAll();

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
            this.__maximizeIFrame(true);
          }, this);
          iFrame.addListener("restore", e => {
            this.__maximizeIFrame(false);
          }, this);
          this.__maximizeIFrame(iFrame.hasState("maximized"));
          this.__iFrameLayout.add(tabView, {
            flex: 1
          });
        }
      });

      this.__addToMainView(this.__iFrameLayout, {
        flex: 1
      });
    },

    __maximizeIFrame: function(maximize) {
      const othersStatus = maximize ? "excluded" : "visible";
      this.__settingsLayout.setVisibility(othersStatus);
      this.__mapperLayout.setVisibility(othersStatus);
      this.__toolbar.setVisibility(othersStatus);
    },

    __hasIFrame: function() {
      return (this.isPropertyInitialized("node") && this.getNode().getIFrame());
    },

    restoreIFrame: function() {
      if (this.__hasIFrame()) {
        const iFrame = this.getNode().getIFrame();
        if (iFrame) {
          iFrame.maximizeIFrame(false);
        }
      }
    },

    __addButtons: function() {
      this.__buttonContainer.removeAll();
      let retrieveIFrameButton = this.getNode().getRetrieveIFrameButton();
      if (retrieveIFrameButton) {
        this.__buttonContainer.add(retrieveIFrameButton);
      }
      let restartIFrameButton = this.getNode().getRestartIFrameButton();
      if (restartIFrameButton) {
        this.__buttonContainer.add(restartIFrameButton);
      }
      this.__toolbar.add(this.__buttonContainer);
    },

    __openNodeDataManager: function() {
      const nodeDataManager = new osparc.component.widget.NodeDataManager(this.getNode(), false);
      const win = nodeDataManager.getWindow();
      win.open();
    },

    __openServiceInfo: function() {
      const win = new osparc.component.metadata.ServiceInfoWindow(this.getNode().getMetaData());
      win.center();
      win.open();
    },

    __attachEventHandlers: function() {
      const maximizeIframeCb = msg => {
        this.__blocker.setStyles({
          display: msg.getData() ? "none" : "block"
        });
      };

      this.addListener("appear", () => {
        qx.event.message.Bus.getInstance().subscribe("maximizeIframe", maximizeIframeCb, this);
      }, this);

      this.addListener("disappear", () => {
        qx.event.message.Bus.getInstance().unsubscribe("maximizeIframe", maximizeIframeCb, this);
      }, this);
    },

    _applyNode: function(node) {
      if (!node.isContainer()) {
        console.error("Only group nodes are supported");
      }
    }
  }
});
