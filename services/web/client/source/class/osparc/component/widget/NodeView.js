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
 *   let nodeView = new osparc.component.widget.NodeView();
 *   nodeView.setNode(workbench.getNode1());
 *   nodeView.populateLayout();
 *   this.getRoot().add(nodeView);
 * </pre>
 */

qx.Class.define("osparc.component.widget.NodeView", {
  extend: qx.ui.splitpane.Pane,

  construct: function() {
    this.base(arguments);

    this.__buildLayout();

    this.__attachEventHandlers();
  },

  statics: {
    createSettingsGroupBox: function(label) {
      const settingsGroupBox = new qx.ui.groupbox.GroupBox(label).set({
        appearance: "settings-groupbox",
        maxWidth: 500,
        alignX: "center",
        layout: new qx.ui.layout.VBox()
      });
      return settingsGroupBox;
    }
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

      this.__settingsLayout = this.self().createSettingsGroupBox(this.tr("Settings"));
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
      const buttonsPart = this.__buttonContainer = new qx.ui.toolbar.Part();
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

      const filesBtn = this.__filesButton = new qx.ui.toolbar.Button(this.tr("Files"), "@FontAwesome5Solid/folder-open/14");
      osparc.utils.Utils.setIdToWidget(filesBtn, "nodeViewFilesBtn");
      buttonsPart.add(filesBtn);

      filesBtn.addListener("execute", () => this.__openNodeDataManager(), this);

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
      this.__addMapper();
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

    __addToMainView: function(view) {
      if (view.hasChildren()) {
        this.__mainView.add(view, {
          flex: 1
        });
      } else if (qx.ui.core.Widget.contains(this.__mainView, view)) {
        this.__mainView.remove(view);
      }
    },

    __addSettings: function() {
      this.__settingsLayout.removeAll();

      const node = this.getNode();
      const propsWidget = node.getPropsWidget();
      if (propsWidget && Object.keys(node.getInputs()).length) {
        this.__settingsLayout.add(propsWidget);
      }

      this.__addToMainView(this.__settingsLayout);
    },

    __addMapper: function() {
      this.__mapperLayout.removeAll();

      const mapper = this.getNode().getInputsMapper();
      if (mapper) {
        this.__mapperLayout.add(mapper, {
          flex: 1
        });
      }

      this.__addToMainView(this.__mapperLayout);
    },

    __addIFrame: function() {
      this.__iFrameLayout.removeAll();

      const iFrame = this.getNode().getIFrame();
      if (iFrame) {
        iFrame.addListener("maximize", e => {
          this.__maximizeIFrame(true);
        }, this);
        iFrame.addListener("restore", e => {
          this.__maximizeIFrame(false);
        }, this);
        this.__maximizeIFrame(iFrame.hasState("maximized"));
        this.__iFrameLayout.add(iFrame, {
          flex: 1
        });
      }

      this.__addToMainView(this.__iFrameLayout);
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
      this.__buttonContainer.add(this.__filesButton);
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
      this.__blocker.addListener("tap", this.__inputsView.toggleCollapsed.bind(this.__inputsView));

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
      if (node.isContainer()) {
        console.error("Only non-group nodes are supported");
      }
    }
  }
});
