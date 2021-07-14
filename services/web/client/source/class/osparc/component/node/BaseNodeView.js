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
    HEADER_HEIGHT: 35,

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
    __nodeStatusUI: null,
    __header: null,
    _mainView: null,
    __inputsView: null,
    __outputsView: null,
    __inputNodesLayout: null,
    _settingsLayout: null,
    _iFrameLayout: null,
    _loggerLayout: null,
    __buttonContainer: null,
    __outFilesButton: null,

    populateLayout: function() {
      this.__cleanLayout();

      this.getNode().bind("label", this.__title, "value");
      this.__addInputPortsUIs();
      this.__addOutputPortsUIs();
      this._addSettings();
      this._addIFrame();
      // this._addLogger();

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
        minWidth: 220,
        collapsedMinWidth: collapsedWidth,
        collapsedWidth: collapsedWidth
      });
      sidePanel.getLayout().resetSeparator();

      const headerContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
        alignY: "middle"
      })).set({
        height: this.self().HEADER_HEIGHT,
        paddingLeft: 10,
        backgroundColor: "material-button-background"
      });
      const titleLabel = new qx.ui.basic.Label(isInput ? this.tr("Inputs") : this.tr("Outputs")).set({
        font: "text-14"
      });
      headerContainer.add(titleLabel);
      sidePanel.add(headerContainer);

      const container = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      const scroll = new qx.ui.container.Scroll();
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

      const collapsedView = this.__buildCollapsedSideView(isInput);
      sidePanel.setCollapsedView(collapsedView);

      return sidePanel;
    },

    __buildCollapsedSideView: function(isInput) {
      const text = isInput ? this.tr("Inputs") : this.tr("Outputs");
      const minWidth = isInput ? 120 : 130;
      const view = isInput ? this.__inputsView : this.__outputsView;
      const container = isInput ? this.__inputNodesLayout : this.__outputNodesLayout;

      const collapsedView = new qx.ui.basic.Atom().set({
        label: text + " (0)",
        iconPosition: "right",
        gap: 6,
        padding: 8,
        alignX: "center",
        alignY: "middle",
        minWidth: minWidth,
        font: "title-14"
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
      this._iFrameLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      this._loggerLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox());

      return mainView;
    },

    __buildHeader: function() {
      const header = this.__header = new qx.ui.container.Composite(new qx.ui.layout.HBox(10)).set({
        height: this.self().HEADER_HEIGHT,
        backgroundColor: "material-button-background"
      });

      const infoLayout = this.__serviceInfoLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      header.add(infoLayout);

      const nodeEditLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const title = this.__title = new osparc.ui.form.EditLabel().set({
        maxWidth: 180,
        labelFont: "text-14",
        inputFont: "text-14",
        editable: osparc.data.Permissions.getInstance().canDo("study.node.rename") && !study.isReadOnly()
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
      nodeEditLayout.add(title);

      if (osparc.data.Permissions.getInstance().canDo("study.node.update") &&
        osparc.data.model.Study.isOwner(study) &&
        !study.isReadOnly()) {
        const editAccessLevel = new qx.ui.form.Button(this.tr("Edit"), "@FontAwesome5Solid/edit/14");
        editAccessLevel.addListener("execute", () => this._openEditAccessLevel(), this);
        nodeEditLayout.add(editAccessLevel);
      }
      header.add(nodeEditLayout);

      header.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      // just a placeholder until the node is set
      const nodeStatusUI = this.__nodeStatusUI = new qx.ui.core.Widget();
      header.add(nodeStatusUI);

      header.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      const buttonsLayout = this.__buttonContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      const filesBtn = this.__outFilesButton = new qx.ui.form.Button(this.tr("Output Files"), "@FontAwesome5Solid/folder-open/14");
      osparc.utils.Utils.setIdToWidget(filesBtn, "nodeViewFilesBtn");
      filesBtn.addListener("execute", () => this.__openNodeDataManager(), this);
      buttonsLayout.add(filesBtn);

      return header;
    },

    __getInfoButton: function() {
      const infoBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/info-circle/14");
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
        const inputNode = study.getWorkbench().getNode(inputNodes[i]);
        if (inputNode) {
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
      if (this.getNode().isDynamic()) {
        const retrieveBtn = new qx.ui.form.Button(this.tr("Retrieve"), "@FontAwesome5Solid/spinner/14");
        osparc.utils.Utils.setIdToWidget(retrieveBtn, "nodeViewRetrieveBtn");
        retrieveBtn.addListener("execute", e => {
          this.getNode().callRetrieveInputs();
        }, this);
        this.getNode().bind("serviceUrl", retrieveBtn, "enabled", {
          converter: value => Boolean(value)
        });
        retrieveBtn.setEnabled(Boolean(this.getNode().getServiceUrl()));
        this.__buttonContainer.add(retrieveBtn);
      }
      this.__buttonContainer.add(this.__outFilesButton);
      this.__header.add(this.__buttonContainer);
    },

    _maximizeIFrame: function(maximize) {
      const othersStatus = maximize ? "excluded" : "visible";
      this.__inputNodesLayout.setVisibility(othersStatus);
      this.__outputNodesLayout.setVisibility(othersStatus);
      const isSettingsGroupShowable = this.isSettingsGroupShowable();
      const othersStatus2 = isSettingsGroupShowable && !maximize ? "visible" : "excluded";
      this._settingsLayout.setVisibility(othersStatus2);
      this._loggerLayout.setVisibility(othersStatus);
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
      const nodeDataManager = new osparc.component.widget.NodeDataManager(this.getNode());
      const win = osparc.ui.window.Window.popUpInWindow(nodeDataManager, this.getNode().getLabel(), 900, 600).set({
        appearance: "service-window"
      });
      const closeBtn = win.getChildControl("close-button");
      osparc.utils.Utils.setIdToWidget(closeBtn, "nodeDataManagerCloseBtn");
    },

    __openServiceDetails: function() {
      const serviceDetails = new osparc.servicecard.Large(this.getNode().getMetaData());
      const title = this.tr("Service information");
      const width = 600;
      const height = 700;
      osparc.ui.window.Window.popUpInWindow(serviceDetails, title, width, height);
    },

    getInputsView: function() {
      return this.__inputsView;
    },

    getOutputsView: function() {
      return this.__outputsView;
    },

    __attachEventHandlers: function() {
      const inputBlocker = this.getBlocker();
      const outputBlocker = this.__pane2.getBlocker();
      inputBlocker.addListener("tap", this.__inputsView.toggleCollapsed.bind(this.__inputsView));
      outputBlocker.addListener("tap", this.__outputsView.toggleCollapsed.bind(this.__outputsView));

      this.addListenerOnce("appear", () => {
        const inputSplitter = this.getChildControl("splitter");
        const inputKnob = inputSplitter.getChildControl("knob");
        inputKnob.set({
          visibility: "visible"
        });
        this.__inputsView.bind("collapsed", inputKnob, "source", {
          converter: collapsed => collapsed ? "@FontAwesome5Solid/angle-double-right/12" : "@FontAwesome5Solid/angle-double-left/12"
        });
        this.__fillUpSplittersGap(inputSplitter);
      }, this);

      this.__pane2.addListenerOnce("appear", () => {
        const outputSplitter = this.__pane2.getChildControl("splitter");
        const outputKnob = outputSplitter.getChildControl("knob");
        outputKnob.set({
          visibility: "visible"
        });
        this.__outputsView.bind("collapsed", outputKnob, "source", {
          converter: collapsed => collapsed ? "@FontAwesome5Solid/angle-double-left/12" : "@FontAwesome5Solid/angle-double-right/12"
        });
        this.__fillUpSplittersGap(outputSplitter);
      }, this);

      const maximizeIframeCb = msg => {
        inputBlocker.setStyles({
          display: msg.getData() ? "none" : "block"
        });
        outputBlocker.setStyles({
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

    // fill up the gap created on top of the slider when the knob image was added
    __fillUpSplittersGap: function(splitter) {
      const headerExtender = new qx.ui.core.Widget().set({
        backgroundColor: "material-button-background",
        height: this.self().HEADER_HEIGHT,
        maxWidth: 12
      });
      // eslint-disable-next-line no-underscore-dangle
      splitter._addAt(headerExtender, 0, {
        flex: 0
      });
      // eslint-disable-next-line no-underscore-dangle
      splitter._addAt(new qx.ui.core.Spacer(), 1, {
        flex: 1
      });
      // knob goes in second postion
      // eslint-disable-next-line no-underscore-dangle
      splitter._addAt(new qx.ui.core.Spacer(), 3, {
        flex: 1
      });
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

    _addLogger: function() {
      return;
    },

    /**
      * @abstract
      */
    _openEditAccessLevel: function() {
      throw new Error("Abstract method called!");
    },

    __createNodeStatusUI: function(node) {
      const nodeStatusUI = new osparc.ui.basic.NodeStatusUI(node).set({
        backgroundColor: "material-button-background"
      });
      nodeStatusUI.getChildControl("label").set({
        font: "text-14"
      });
      return nodeStatusUI;
    },

    /**
      * @param node {osparc.data.model.Node} node
      */
    _applyNode: function(node) {
      this.__serviceInfoLayout.removeAll();
      if (node && node.getMetaData()) {
        const infoButton = this.__getInfoButton();
        this.__serviceInfoLayout.add(infoButton);
      }

      const idx = this.__header.indexOf(this.__nodeStatusUI);
      if (idx > -1) {
        this.__header.remove(this.__nodeStatusUI);
      }
      this.__nodeStatusUI = this.__createNodeStatusUI(node);
      this.__header.addAt(this.__nodeStatusUI, idx);
    }
  }
});
