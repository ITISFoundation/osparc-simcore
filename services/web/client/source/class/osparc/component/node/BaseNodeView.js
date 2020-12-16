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
    __serviceInfoLayout: null,
    __header: null,
    _mainView: null,
    __inputsView: null,
    __outputsView: null,
    __inputNodesLayout: null,
    _settingsLayout: null,
    _mapperLayout: null,
    _iFrameLayout: null,
    __buttonContainer: null,
    __filesButton: null,

    populateLayout: function() {
      this.__cleanLayout();

      this.getNode().bind("label", this.__title, "value");
      this.__addInputPortsUIs();
      this.__addOutputPortsUIs();
      this._addSettings();
      this._addIFrame();
      this._addButtons();
    },

    __buildLayout: function() {
      const inputs = this.__buildSideView(true);

      const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
      const header = this.__buildHeader();
      const mainView = this.__buildMainView();
      vBox.add(header);
      vBox.add(mainView, {
        flex: 1
      });

      const outputs = this.__buildSideView(false);

      const pane2 = this.__pane2 = new qx.ui.splitpane.Pane();
      this.add(inputs, 0); // flex 0
      this.add(pane2, 1); // flex 1

      pane2.add(vBox, 1); // flex 1
      pane2.add(outputs, 0); // flex 0
    },

    __cleanLayout: function() {
      this._mainView.removeAll();
    },

    __buildSideView: function(isInput) {
      const collapsedWidth = 35;
      const sidePanel = new osparc.desktop.SidePanel().set({
        minWidth: 250,
        collapsedMinWidth: collapsedWidth,
        collapsedWidth: collapsedWidth
      });

      const sideHeader = new qx.ui.toolbar.ToolBar();
      const titlePart = new qx.ui.toolbar.Part();
      const buttonPart = new qx.ui.toolbar.Part();
      sideHeader.add(titlePart);
      sideHeader.addSpacer();
      sideHeader.add(buttonPart);
      this.add(sideHeader, 0);
      titlePart.add(new qx.ui.basic.Label(isInput ? this.tr("Inputs") : this.tr("Outputs")).set({
        alignY: "middle",
        font: "text-16"
      }));
      const collapseBtn = new qx.ui.toolbar.Button(this.tr("Collapse all"), "@FontAwesome5Solid/minus-square/14");
      buttonPart.add(collapseBtn);
      sidePanel.add(sideHeader);

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
      sidePanel.setCollapsedView(collapsedView);

      return sidePanel;
    },

    __buildCollapsedSideView: function(isInput) {
      const text = isInput ? this.tr("Inputs") : this.tr("Outputs");
      const icon = isInput ? "@FontAwesome5Solid/chevron-down/12" : "@FontAwesome5Solid/chevron-up/12";
      const minWidth = isInput ? 120 : 130;
      const view = isInput ? this.__inputsView : this.__outputsView;
      const container = isInput ? this.__inputNodesLayout : this.__outputNodesLayout;

      const collapsedView = new qx.ui.basic.Atom().set({
        label: text + " (0)",
        icon: icon,
        iconPosition: "right",
        gap: 6,
        padding: 8,
        alignX: "center",
        alignY: "middle",
        minWidth: minWidth,
        font: "title-18"
      });
      collapsedView.getContentElement().addClass("verticalText");
      collapsedView.addListener("tap", view.toggleCollapsed.bind(view));
      collapsedView.addListenerOnce("appear", () => {
        const elem = collapsedView.getContentElement();
        console.log(elem);
        // const size = qx.bom.element.Dimension.getSize(collapsedView);
        // collapsedView.setDomLeft(-1 * (size.width/2) - (size.height/2));
        collapsedView.setDomLeft(-45);
      });

      [
        "addChildWidget",
        "removeChildWidget"
      ].forEach(event => {
        container.addListener(event, () => {
          const nChildren = container.getChildren().length;
          collapsedView.setLabel(text + " (" + nChildren + ")");
        });
      });

      return collapsedView;
    },

    __buildMainView: function() {
      const mainView = this._mainView = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      this._settingsLayout = this.self().createSettingsGroupBox(this.tr("Settings"));
      this._mapperLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
      this._iFrameLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox());

      return mainView;
    },

    __buildHeader: function() {
      const header = this.__header = new qx.ui.toolbar.ToolBar().set({
        spacing: 20
      });

      const nodeEditPart = new qx.ui.toolbar.Part().set({
        spacing: 10
      });
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const title = this.__title = new osparc.ui.form.EditLabel().set({
        maxWidth: 180,
        labelFont: "text-16",
        inputFont: "text-16",
        editable: osparc.data.Permissions.getInstance().canDo("study.node.rename")
      });
      title.addListener("editValue", evt => {
        if (evt.getData() !== this.__title.getValue()) {
          const node = this.getNode();
          if (node) {
            node.renameNode(evt.getData());
          }
          qx.event.message.Bus.getInstance().dispatchByName("updateStudy", study.serialize());
        }
      }, this);
      nodeEditPart.add(title);

      if (osparc.data.Permissions.getInstance().canDo("study.node.update") && osparc.data.model.Study.isOwner(study)) {
        const editAccessLevel = new qx.ui.toolbar.Button(this.tr("Edit"), "@FontAwesome5Solid/edit/14");
        editAccessLevel.addListener("execute", () => this._openEditAccessLevel(), this);
        nodeEditPart.add(editAccessLevel);
      }
      header.add(nodeEditPart);

      header.addSpacer();

      const nameVersionPart = this.__serviceInfoLayout = new qx.ui.toolbar.Part();
      header.add(nameVersionPart);

      header.addSpacer();

      const buttonsPart = this.__buttonContainer = new qx.ui.toolbar.Part();
      const filesBtn = this.__filesButton = new qx.ui.toolbar.Button(this.tr("Output Files"), "@FontAwesome5Solid/folder-open/14");
      osparc.utils.Utils.setIdToWidget(filesBtn, "nodeViewFilesBtn");
      filesBtn.addListener("execute", () => this.__openNodeDataManager(), this);
      buttonsPart.add(filesBtn);

      return header;
    },

    __getInfoButton: function() {
      const infoBtn = new qx.ui.toolbar.Button(null, "@FontAwesome5Solid/info-circle/14");
      infoBtn.addListener("execute", () => this.__openServiceDetails(), this);
      return infoBtn;
    },

    _addToMainView: function(view, options = {}) {
      if (view.hasChildren()) {
        this._mainView.add(view, options);
      } else if (qx.ui.core.Widget.contains(this._mainView, view)) {
        this._mainView.remove(view);
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
      const nodePorts = isInputModel ? inputNode.getOutputWidget() : inputNode.getInputsDefaultWidget();
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
      if (this.getNode().isDynamic() && this.getNode().isRealService()) {
        const retrieveBtn = new qx.ui.toolbar.Button(this.tr("Retrieve"), "@FontAwesome5Solid/spinner/14");
        osparc.utils.Utils.setIdToWidget(retrieveBtn, "nodeViewRetrieveBtn");
        retrieveBtn.addListener("execute", e => {
          this.getNode().retrieveInputs();
        }, this);
        this.getNode().bind("serviceUrl", retrieveBtn, "enabled", {
          converter: value => Boolean(value)
        });
        retrieveBtn.setEnabled(Boolean(this.getNode().getServiceUrl()));
        this.__buttonContainer.add(retrieveBtn);
      }
      this.__buttonContainer.add(this.__filesButton);
      this.__header.add(this.__buttonContainer);
    },

    _maximizeIFrame: function(maximize) {
      const othersStatus = maximize ? "excluded" : "visible";
      this.__inputNodesLayout.setVisibility(othersStatus);
      this.__outputNodesLayout.setVisibility(othersStatus);
      const isSettingsGroupShowable = this.isSettingsGroupShowable();
      const othersStatus2 = isSettingsGroupShowable && !maximize ? "visible" : "excluded";
      this._settingsLayout.setVisibility(othersStatus2);
      this._mapperLayout.setVisibility(othersStatus);
      this.__header.setVisibility(othersStatus);
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

    __openServiceDetails: function() {
      const serviceDetails = new osparc.component.metadata.ServiceDetails(this.getNode().getMetaData());
      const title = qx.locale.Manager.tr("Service information") + " · " + serviceDetails.getService().name;
      osparc.ui.window.Window.popUpInWindow(serviceDetails, title, 700, 800);
    },

    getInputsView: function() {
      return this.__inputsView;
    },

    getOutputsView: function() {
      return this.__outputsView;
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
      * @param node {osparc.data.model.Node} node
      */
    _applyNode: function(node) {
      this.__serviceInfoLayout.removeAll();
      if (node && node.getMetaData()) {
        const metadata = node.getMetaData();
        const label = new qx.ui.basic.Label(metadata.name + " : " + metadata.version).set({
          enabled: false,
          alignY: "middle"
        });
        this.__serviceInfoLayout.add(label);

        const infoButton = this.__getInfoButton();
        this.__serviceInfoLayout.add(infoButton);
      }
    }
  }
});
