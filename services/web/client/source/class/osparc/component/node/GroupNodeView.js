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
    __inputsView: null,
    __inputNodesLayout: null,
    __collapseBtn: null,
    __settingsLayout: null,
    __mapperLayout: null,
    __iFrameLayout: null,
    __buttonContainer: null,
    __filesButton: null,

    __buildInputsView: function() {
      const inputsView = this.__inputsView = new osparc.desktop.SidePanel().set({
        minWidth: 300
      });
      const titleBar = new qx.ui.toolbar.ToolBar();
      const titlePart = new qx.ui.toolbar.Part();
      const buttonPart = new qx.ui.toolbar.Part();
      titleBar.add(titlePart);
      titleBar.addSpacer();
      titleBar.add(buttonPart);
      this.add(titleBar, 0);
      titlePart.add(new qx.ui.basic.Atom(this.tr("Inputs")).set({
        font: "title-18"
      }));
      const collapseBtn = this.__collapseBtn = new qx.ui.toolbar.Button(this.tr("Collapse all"), "@FontAwesome5Solid/minus-square/14");
      buttonPart.add(collapseBtn);
      inputsView.add(titleBar);

      const scroll = new qx.ui.container.Scroll();
      const inputContainer = this.__inputNodesLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      scroll.add(inputContainer);
      inputsView.add(scroll, {
        flex: 1
      });

      this.add(inputsView, 0);
    },

    __buildMainView: function() {
      const mainView = this.__mainView = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
      this.add(mainView, 1);

      this.__settingsLayout = osparc.component.node.NodeView.createSettingsGroupBox(this.tr("Settings"));
      this.__mapperLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
      this.__iFrameLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox());

      mainView.add(this.__initToolbar());
    },

    __buildLayout: function() {
      this.__buildInputsView();
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
      this.__addInputPortsUIs();
      this.__addSettings();
      this.__addIFrame();
      this.__addButtons();
    },

    __addInputPortsUIs: function() {
      this.__inputNodesLayout.removeAll();

      // Add the default inputs if any
      if (Object.keys(this.getNode().getInputsDefault()).length > 0) {
        this.__createInputPortsUI(this.getNode(), false);
      }

      // Add the representations for the inputs
      const inputNodes = this.getNode().getInputNodes();
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      for (let i=0; i<inputNodes.length; i++) {
        let inputNode = study.getWorkbench().getNode(inputNodes[i]);
        if (inputNode.isContainer()) {
          const exposedInnerNodes = inputNode.getExposedInnerNodes();
          for (const exposedInnerNodeId in exposedInnerNodes) {
            const exposedInnerNode = exposedInnerNodes[exposedInnerNodeId];
            this.__createInputPortsUI(exposedInnerNode);
          }
        } else {
          this.__createInputPortsUI(inputNode);
        }
      }
    },

    __createInputPortsUI: function(inputNode, isInputModel = true) {
      let nodePorts = null;
      if (isInputModel) {
        nodePorts = inputNode.getOutputWidget();
      } else {
        nodePorts = inputNode.getInputsDefaultWidget();
      }
      if (nodePorts) {
        this.__inputNodesLayout.add(nodePorts, {
          flex: 1
        });
        nodePorts.setCollapsed(false);
      }
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
      this.__mapperLayout.removeAll();

      const innerNodes = this.getNode().getInnerNodes(true);
      Object.values(innerNodes).forEach(innerNode => {
        const innerSettings = osparc.component.node.NodeView.createSettingsGroupBox();
        innerNode.bind("label", innerSettings, "legend");
        const propsWidget = innerNode.getPropsWidget();
        if (propsWidget && Object.keys(innerNode.getInputs()).length) {
          innerSettings.add(propsWidget);
          this.__settingsLayout.add(innerSettings);
        }
        const mapper = innerNode.getInputsMapper();
        if (mapper) {
          this.__mapperLayout.add(mapper, {
            flex: 1
          });
        }
      });

      this.__addToMainView(this.__settingsLayout);
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
      this.__inputNodesLayout.setVisibility(othersStatus);
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
        this.__inputsView.setVisibility(msg.getData() ? "excluded" : "visible");
      };

      this.addListener("appear", () => {
        qx.event.message.Bus.getInstance().subscribe("maximizeIframe", maximizeIframeCb, this);
      }, this);

      this.addListener("disappear", () => {
        qx.event.message.Bus.getInstance().unsubscribe("maximizeIframe", maximizeIframeCb, this);
      }, this);

      this.__collapseBtn.addListener("execute", () => {
        this.__inputNodesLayout.getChildren().forEach(node => {
          node.setCollapsed(true);
        });
      }, this);
    },

    _applyNode: function(node) {
      if (!node.isContainer()) {
        console.error("Only group nodes are supported");
      }
    }
  }
});
