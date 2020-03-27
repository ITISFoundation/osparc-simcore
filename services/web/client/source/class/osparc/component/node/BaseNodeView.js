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
 */

qx.Class.define("osparc.component.node.BaseNodeView", {
  extend: qx.ui.splitpane.Pane,
  type: "abstract",

  construct: function() {
    this.base(arguments);

    this.__buildLayout();

    this.__attachEventHandlers();
  },

  statics: {
    createSettingsGroupBox: function(label) {
      const settingsGroupBox = new qx.ui.groupbox.GroupBox(label).set({
        appearance: "settings-groupbox",
        maxWidth: 800,
        alignX: "center",
        layout: new qx.ui.layout.VBox()
      });
      return settingsGroupBox;
    },

    createWindow: function(label) {
      const win = new qx.ui.window.Window(label).set({
        layout: new qx.ui.layout.Grow(),
        contentPadding: 10,
        showMinimize: false,
        resizable: true,
        modal: true,
        height: 600,
        width: 800
      });
      return win;
    }
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
      apply: "_applyNode",
      nullable: true,
      init: null
    }
  },

  members: {
    __pane2: null,
    __title: null,
    __toolbar: null,
    __mainView: null,
    __inputsView: null,
    __outputsView: null,
    __inputNodesLayout: null,
    _settingsLayout: null,
    _mapperLayout: null,
    _iFrameLayout: null,
    __buttonContainer: null,
    __filesButton: null,

    populateLayout: function() {
      this.getNode().bind("label", this.__title, "value");
      this.__addInputPortsUIs();
      this.__addOutputPortsUIs();
      this._addSettings();
      this._addIFrame();
      this._addButtons();
    },

    __buildLayout: function() {
      const inputs = this.__buildSideView(true);
      const mainView = this.__buildMainView();
      const outputs = this.__buildSideView(false);

      const pane2 = this.__pane2 = new qx.ui.splitpane.Pane();
      this.add(inputs, 0); // flex 0
      this.add(pane2, 1); // flex 1

      pane2.add(mainView, 1); // flex 1
      pane2.add(outputs, 0); // flex 0
    },

    __buildSideView: function(isInput) {
      const collapsedWidth = 35;
      const sidePanel = new osparc.desktop.SidePanel().set({
        minWidth: 300,
        collapsedMinWidth: collapsedWidth,
        collapsedWidth: collapsedWidth
      });

      const titleBar = new qx.ui.toolbar.ToolBar();
      const titlePart = new qx.ui.toolbar.Part();
      const buttonPart = new qx.ui.toolbar.Part();
      titleBar.add(titlePart);
      titleBar.addSpacer();
      titleBar.add(buttonPart);
      this.add(titleBar, 0);
      titlePart.add(new qx.ui.basic.Label(isInput ? this.tr("Inputs") : this.tr("Outputs")).set({
        alignY: "middle",
        font: "title-18"
      }));
      const collapseBtn = new qx.ui.toolbar.Button(this.tr("Collapse all"), "@FontAwesome5Solid/minus-square/14");
      buttonPart.add(collapseBtn);
      sidePanel.add(titleBar);

      const scroll = new qx.ui.container.Scroll();
      const container = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      scroll.add(container);
      sidePanel.add(scroll, {
        flex: 1
      });

      if (isInput) {
        this.__inputsView = sidePanel;
        this.__inputNodesLayout = container;
      } else {
        this.__outputsView = sidePanel;
        this.__outputNodesLayout = container;
      }
      collapseBtn.addListener("execute", () => {
        container.getChildren().forEach(node => {
          node.setCollapsed(true);
        });
      }, this);

      const collapsedView = this.__buildCollapsedSideView(isInput);
      collapsedView.addListenerOnce("appear", () => {
        const elem = collapsedView.getContentElement();
        console.log(elem);
        // const size = qx.bom.element.Dimension.getSize(collapsedView);
        // collapsedView.setDomLeft(-1 * (size.width/2) - (size.height/2));
        collapsedView.setDomLeft(-45);
      });
      sidePanel.setCollapsedView(collapsedView);

      return sidePanel;
    },

    __buildCollapsedSideView: function(isInput) {
      const inText = this.tr("Inputs");
      const outText = this.tr("Outputs");
      const inIcon = "@FontAwesome5Solid/chevron-down/12";
      const outIcon = "@FontAwesome5Solid/chevron-up/12";
      const collapsedView = new qx.ui.basic.Atom().set({
        label: (isInput ? inText : outText) + " (0)",
        icon: isInput ? inIcon : outIcon,
        iconPosition: "right",
        gap: 6,
        padding: 8,
        alignX: "center",
        alignY: "middle",
        minWidth: isInput ? 120 : 130,
        font: "title-18"
      });
      collapsedView.getContentElement().addClass("verticalText");
      const view = isInput ? this.__inputsView : this.__outputsView;
      collapsedView.addListener("tap", view.toggleCollapsed.bind(view));

      const container = isInput ? this.__inputNodesLayout : this.__outputNodesLayout;
      [
        "addChildWidget",
        "removeChildWidget"
      ].forEach(event => {
        container.addListener(event, () => {
          const nChildren = container.getChildren().length;
          collapsedView.setLabel((isInput ? inText : outText) + " (" + nChildren + ")");
        });
      });

      return collapsedView;
    },

    __buildMainView: function() {
      const mainView = this.__mainView = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      this._settingsLayout = this.self().createSettingsGroupBox(this.tr("Settings"));
      this._mapperLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
      this._iFrameLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox());

      mainView.add(this.__buildToolbar());

      return mainView;
    },

    __buildToolbar: function() {
      const toolbar = this.__toolbar = new qx.ui.toolbar.ToolBar();
      const titlePart = new qx.ui.toolbar.Part();
      const infoPart = new qx.ui.toolbar.Part();
      const buttonsPart = this.__buttonContainer = new qx.ui.toolbar.Part();
      toolbar.add(titlePart);
      toolbar.add(infoPart);
      toolbar.addSpacer();

      const title = this.__title = new osparc.ui.form.EditLabel().set({
        labelFont: "title-18",
        inputFont: "text-18",
        editable: osparc.data.Permissions.getInstance().canDo("study.node.rename")
      });
      title.addListener("editValue", evt => {
        if (evt.getData() !== this.__title.getValue()) {
          const node = this.getNode();
          if (node) {
            node.renameNode(evt.getData());
          }
          const study = osparc.store.Store.getInstance().getCurrentStudy();
          qx.event.message.Bus.getInstance().dispatchByName("updateStudy", study.serializeStudy());
        }
      }, this);
      titlePart.add(title);

      const infoBtn = new qx.ui.toolbar.Button(this.tr("Info"), "@FontAwesome5Solid/info-circle/14");
      infoBtn.addListener("execute", () => this.__openServiceInfo(), this);
      infoPart.add(infoBtn);

      if (osparc.data.Permissions.getInstance().canDo("study.node.update")) {
        const editAccessLevel = new qx.ui.toolbar.Button(this.tr("Edit Access Level"));
        editAccessLevel.addListener("execute", () => this._openEditAccessLevel(), this);
        infoPart.add(editAccessLevel);
      }

      const filesBtn = this.__filesButton = new qx.ui.toolbar.Button(this.tr("Files"), "@FontAwesome5Solid/folder-open/14");
      osparc.utils.Utils.setIdToWidget(filesBtn, "nodeViewFilesBtn");
      filesBtn.addListener("execute", () => this.__openNodeDataManager(), this);
      buttonsPart.add(filesBtn);

      return toolbar;
    },

    _addToMainView: function(view, options = {}) {
      if (view.hasChildren()) {
        this.__mainView.add(view, options);
      } else if (qx.ui.core.Widget.contains(this.__mainView, view)) {
        this.__mainView.remove(view);
      }
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

    __addOutputPortsUIs: function() {
      this.__outputNodesLayout.removeAll();

      // Add the representations for the outputs
      if (this.getNode().isContainer()) {
        const exposedInnerNodes = this.getNode().getExposedInnerNodes();
        for (const exposedInnerNodeId in exposedInnerNodes) {
          const exposedInnerNode = exposedInnerNodes[exposedInnerNodeId];
          this.__createOutputPortsUI(exposedInnerNode);
        }
      } else {
        this.__createOutputPortsUI(this.getNode());
      }
    },

    __createOutputPortsUI: function(outputNode) {
      const nodePorts = outputNode.getOutputWidget();
      if (nodePorts) {
        this.__outputNodesLayout.add(nodePorts, {
          flex: 1
        });
        nodePorts.setCollapsed(false);
      }
    },

    _addButtons: function() {
      this.__buttonContainer.removeAll();
      let retrieveIFrameButton = this.getNode().getRetrieveIFrameButton();
      if (retrieveIFrameButton) {
        this.__buttonContainer.add(retrieveIFrameButton);
      }
      this.__buttonContainer.add(this.__filesButton);
      this.__toolbar.add(this.__buttonContainer);
    },

    _maximizeIFrame: function(maximize) {
      const othersStatus = maximize ? "excluded" : "visible";
      this.__inputNodesLayout.setVisibility(othersStatus);
      this.__outputNodesLayout.setVisibility(othersStatus);
      const isSettingsGroupShowable = this.isSettingsGroupShowable();
      const othersStatus2 = isSettingsGroupShowable && !maximize ? "visible" : "excluded";
      this._settingsLayout.setVisibility(othersStatus2);
      this._mapperLayout.setVisibility(othersStatus);
      this.__toolbar.setVisibility(othersStatus);
    },

    __hasIFrame: function() {
      return (this.isPropertyInitialized("node") && this.getNode() && this.getNode().getIFrame());
    },

    restoreIFrame: function() {
      if (this.__hasIFrame()) {
        const iFrame = this.getNode().getIFrame();
        if (iFrame) {
          iFrame.maximizeIFrame(false);
        }
      }
    },

    __openNodeDataManager: function() {
      const nodeDataManager = new osparc.component.widget.NodeDataManager(this.getNode(), true);
      const win = nodeDataManager.getWindow();
      win.open();
    },

    __openServiceInfo: function() {
      const win = new osparc.component.metadata.ServiceInfoWindow(this.getNode().getMetaData());
      win.center();
      win.open();
    },

    __attachEventHandlers: function() {
      const blocker1 = this.getBlocker();
      const blocker2 = this.__pane2.getBlocker();
      blocker1.addListener("tap", this.__inputsView.toggleCollapsed.bind(this.__inputsView));
      blocker2.addListener("tap", this.__outputsView.toggleCollapsed.bind(this.__outputsView));

      const maximizeIframeCb = msg => {
        blocker1.setStyles({
          display: msg.getData() ? "none" : "block"
        });
        blocker2.setStyles({
          display: msg.getData() ? "none" : "block"
        });
        this.__inputsView.setVisibility(msg.getData() ? "excluded" : "visible");
        this.__outputsView.setVisibility(msg.getData() ? "excluded" : "visible");
      };

      this.addListener("appear", () => {
        qx.event.message.Bus.getInstance().subscribe("maximizeIframe", maximizeIframeCb, this);
      }, this);

      this.addListener("disappear", () => {
        qx.event.message.Bus.getInstance().unsubscribe("maximizeIframe", maximizeIframeCb, this);
      }, this);
    },

    /**
      * @abstract
      */
    isSettingsGroupShowable: function() {
      throw new Error("Abstract method called!");
    },

    /**
      * @abstract
      */
    _addSettings: function() {
      throw new Error("Abstract method called!");
    },

    /**
      * @abstract
      */
    _addIFrame: function() {
      throw new Error("Abstract method called!");
    },

    /**
      * @abstract
      */
    _openEditAccessLevel: function() {
      throw new Error("Abstract method called!");
    },

    /**
      * @abstract
      * @param node {osparc.data.model.Node} node
      */
    _applyNode: function(node) {
      throw new Error("Abstract method called!");
    }
  }
});
