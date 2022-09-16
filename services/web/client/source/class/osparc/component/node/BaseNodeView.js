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
    this.base(arguments, "vertical");

    this.setOffset(2);
    osparc.desktop.WorkbenchView.decorateSplitter(this.getChildControl("splitter"));
    osparc.desktop.WorkbenchView.decorateSlider(this.getChildControl("slider"));

    this.__buildLayout();

    this.set({
      paddingBottom: 2
    });
  },

  statics: {
    HEADER_HEIGHT: 32,

    createSettingsGroupBox: function(label) {
      const settingsGroupBox = new qx.ui.groupbox.GroupBox(label).set({
        appearance: "settings-groupbox",
        maxWidth: 800,
        alignX: "center",
        layout: new qx.ui.layout.VBox(10)
      });
      return settingsGroupBox;
    },

    openNodeDataManager: function(node) {
      const nodeDataManager = new osparc.component.widget.NodeDataManager(node);
      nodeDataManager.getChildControl("node-files-tree").exclude();
      const win = osparc.ui.window.Window.popUpInWindow(nodeDataManager, node.getLabel(), 900, 600).set({
        appearance: "service-window"
      });
      const closeBtn = win.getChildControl("close-button");
      osparc.utils.Utils.setIdToWidget(closeBtn, "nodeDataManagerCloseBtn");
    }
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
      apply: "__applyNode",
      nullable: true,
      init: null
    }
  },

  members: {
    _header: null,
    __inputsButton: null,
    __preparingInputs: null,
    __nodeStatusUI: null,
    _mainView: null,
    _settingsLayout: null,
    _iFrameLayout: null,
    _outputsLayout: null,
    __progressBar: null,

    __buildLayout: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(0));

      const header = this._header = this._buildHeader();
      layout.add(header);

      const mainView = this.__buildMainView();
      layout.add(mainView, {
        flex: 1
      });

      const progressBar = this.__progressBar = new qx.ui.core.Widget().set({
        visibility: "excluded",
        allowGrowX: true,
        height: 6
      });
      layout.add(progressBar);

      this.add(layout, 1);
    },

    _buildHeader: function() {
      const header = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignX: "center"
      })).set({
        padding: 6,
        height: this.self().HEADER_HEIGHT
      });


      const inputsStateBtn = this.__inputsButton = new qx.ui.form.Button().set({
        label: this.tr("Inputs"),
        icon: "@FontAwesome5Solid/sign-in-alt/14",
        backgroundColor: "transparent"
      });
      inputsStateBtn.addListener("execute", () => this.showPreparingInputs(), this);
      header.add(inputsStateBtn);

      header.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      const infoBtn = new qx.ui.form.Button(null, "@MaterialIcons/info_outline/16").set({
        backgroundColor: "transparent",
        toolTipText: this.tr("Information")
      });
      infoBtn.addListener("execute", () => this.__openServiceDetails(), this);
      header.add(infoBtn);

      const nodeStatusUI = this.__nodeStatusUI = new osparc.ui.basic.NodeStatusUI().set({
        backgroundColor: "background-main-4"
      });
      nodeStatusUI.getChildControl("label").setFont("text-14");
      header.add(nodeStatusUI);

      header.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      const outputsBtn = this._outputsBtn = new qx.ui.form.ToggleButton().set({
        label: this.tr("Outputs"),
        icon: "@FontAwesome5Solid/sign-out-alt/14",
        backgroundColor: "transparent"
      });
      osparc.utils.Utils.setIdToWidget(outputsBtn, "outputsBtn");
      header.add(outputsBtn);

      return header;
    },

    __buildMainView: function() {
      const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));

      const mainView = this._mainView = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      const settingsBox = this._settingsLayout = this.self().createSettingsGroupBox(this.tr("Settings"));
      mainView.bind("backgroundColor", settingsBox, "backgroundColor");
      mainView.bind("backgroundColor", settingsBox.getChildControl("frame"), "backgroundColor");

      this._iFrameLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox());

      hBox.add(mainView, {
        flex: 1
      });

      const outputsLayout = this._outputsLayout = this.self().createSettingsGroupBox(this.tr("Outputs")).set({
        padding: 4,
        width: 280
      });
      mainView.bind("backgroundColor", outputsLayout, "backgroundColor");
      mainView.bind("backgroundColor", outputsLayout.getChildControl("frame"), "backgroundColor");
      this._outputsBtn.bind("value", outputsLayout, "visibility", {
        converter: value => value ? "visible" : "excluded"
      });
      hBox.add(outputsLayout);

      return hBox;
    },

    showPreparingInputs: function() {
      const title = this.tr("Preparing Inputs");
      const width = 650;
      const height = 600;
      const win = osparc.ui.window.Window.popUpInWindow(this.__preparingInputs, title, width, height);
      const closeBtn = win.getChildControl("close-button");
      osparc.utils.Utils.setIdToWidget(closeBtn, "preparingInputsCloseBtn");
    },

    __openServiceDetails: function() {
      const node = this.getNode();
      const serviceDetails = new osparc.servicecard.Large(node.getMetaData(), {
        nodeId: node.getNodeId(),
        label: node.getLabel(),
        study: node.getStudy()
      });
      const title = this.tr("Service information");
      const width = 600;
      const height = 700;
      osparc.ui.window.Window.popUpInWindow(serviceDetails, title, width, height);
    },

    getHeaderLayout: function() {
      return this._header;
    },

    getOutputsButton: function() {
      return this._outputsBtn;
    },

    getMainView: function() {
      return this._mainView;
    },

    getSettingsLayout: function() {
      return this._settingsLayout;
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

    _addOutputs: function() {
      return;
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

    __areInputsReady: function() {
      const wb = this.getNode().getStudy().getWorkbench();
      const upstreamNodeIds = wb.getUpstreamCompNodes(this.getNode(), false);
      for (let i=0; i<upstreamNodeIds.length; i++) {
        const upstreamNodeId = upstreamNodeIds[i];
        if (!osparc.data.model.NodeStatus.isCompNodeReady(wb.getNode(upstreamNodeId))) {
          return false;
        }
      }
      return true;
    },

    __enableIframeContent: function(enable) {
      this._mainView.setEnabled(enable);
      const iframe = this.getNode().getIFrame();
      if (iframe) {
        // enable/disable user interaction on iframe
        // eslint-disable-next-line no-underscore-dangle
        iframe.__iframe.getContentElement().setStyles({
          "pointer-events": enable ? "auto" : "none"
        });
      }
    },

    setUpstreamDependencies: function(upstreamDependencies = []) {
      this.__inputsButton.setVisibility(upstreamDependencies.length > 0 ? "visible" : "excluded");
      const monitoredNodes = [];
      const workbench = this.getNode().getStudy().getWorkbench();
      upstreamDependencies.forEach(nodeId => monitoredNodes.push(workbench.getNode(nodeId)));
      this.__preparingInputs.setMonitoredNodes(monitoredNodes);
    },

    __dependeciesChanged: function() {
      const preparingNodes = this.__preparingInputs.getPreparingNodes();
      const waiting = Boolean(preparingNodes && preparingNodes.length);
      const buttonsIcon = this.__inputsButton.getChildControl("icon");
      if (waiting) {
        this.__inputsButton.setIcon("@FontAwesome5Solid/circle-notch/14");
        osparc.utils.Utils.addClass(buttonsIcon.getContentElement(), "rotate");
      } else {
        this.__inputsButton.setIcon("@FontAwesome5Solid/sign-in-alt/14");
        osparc.utils.Utils.removeClass(buttonsIcon.getContentElement(), "rotate");
      }
      this.__enableIframeContent(!waiting);
    },

    __applyNode: function(node) {
      if (this.__nodeStatusUI) {
        this.__nodeStatusUI.setNode(node);
      }

      this.__preparingInputs = new osparc.component.widget.PreparingInputs();
      this.__preparingInputs.addListener("changePreparingNodes", () => this.__dependeciesChanged());
      this.__dependeciesChanged();

      this._mainView.removeAll();
      this._addSettings();
      this._addIFrame();
      this._addOutputs();

      if (this.__progressBar) {
        const updateProgress = () => {
          const running = node.getStatus().getRunning();
          const progress = node.getStatus().getProgress();
          if (["PENDING", "PUBLISHED"].includes(running) ||
            (["STARTED"].includes(running) && progress === 0)) {
            this.__progressBar.setBackgroundColor("busy-orange");
            this.__progressBar.getContentElement().setStyles({
              width: "100%"
            });
          } else if (["FAILED", "ABORTED"].includes(running)) {
            this.__progressBar.setBackgroundColor("failed-red");
            this.__progressBar.getContentElement().setStyles({
              width: "100%"
            });
          } else if (["SUCCESS"].includes(running)) {
            this.__progressBar.setBackgroundColor("ready-green");
            this.__progressBar.getContentElement().setStyles({
              width: progress + "%"
            });
          } else {
            this.__progressBar.setBackgroundColor("transparent");
            this.__progressBar.getContentElement().setStyles({
              width: "100%"
            });
          }
        };
        this.__progressBar.setVisibility(node.isComputational() ? "visible" : "excluded");
        updateProgress();
        node.getStatus().addListener("changeRunning", () => updateProgress(), this);
        node.getStatus().addListener("changeProgress", () => updateProgress(), this);
      }

      node.bind("outputs", this._outputsBtn, "label", {
        converter: outputsData => {
          let outputCounter = 0;
          Object.keys(outputsData).forEach(outKey => {
            const outValue = osparc.data.model.Node.getOutput(outputsData, outKey);
            if (![null, undefined, ""].includes(outValue)) {
              outputCounter++;
            }
          });
          return this.tr("Outputs") + ` (${outputCounter})`;
        }
      });
      this._outputsBtn.addListener("changeLabel", () => {
        // make it "blink"
        this._outputsBtn.setTextColor("ready-green");
        setTimeout(() => this._outputsBtn.setTextColor("text"), 1000);
      });

      this._addLogger();
    }
  }
});
