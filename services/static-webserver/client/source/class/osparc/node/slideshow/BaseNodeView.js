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

qx.Class.define("osparc.node.slideshow.BaseNodeView", {
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

  events: {
    "startPartialPipeline": "qx.event.type.Data",
    "stopPipeline": "qx.event.type.Event"
  },

  members: {
    __header: null,
    __inputsButton: null,
    __preparingInputs: null,
    __instructionsBtn: null,
    __instructionsWindow: null,
    __nodeStartButton: null,
    __nodeStopButton: null,
    __nodeStatusUI: null,
    _mainView: null,
    _settingsLayout: null,
    _iFrameLayout: null,
    _outputsLayout: null,
    __progressBar: null,

    __buildLayout: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(0));

      const header = this.__header = this.__buildHeader();
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

    __buildHeader: function() {
      const header = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignX: "center"
      })).set({
        padding: 6,
        paddingTop: 0,
        height: this.self().HEADER_HEIGHT
      });


      const inputsStateBtn = this.__inputsButton = new qx.ui.form.Button().set({
        width: 110,
        label: this.tr("Inputs"),
        icon: "@FontAwesome5Solid/sign-in-alt/14",
        backgroundColor: "background-main-4"
      });
      inputsStateBtn.addListener("execute", () => this.showPreparingInputs(), this);
      header.add(inputsStateBtn);

      header.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      const infoBtn = new qx.ui.form.Button(null, "@MaterialIcons/info_outline/17").set({
        padding: 3,
        backgroundColor: "transparent",
        toolTipText: this.tr("Service Information")
      });
      infoBtn.addListener("execute", () => this.__openServiceDetails(), this);
      header.add(infoBtn);

      const instructionsBtn = this.__instructionsBtn = new qx.ui.form.Button(this.tr("Instructions"), "@FontAwesome5Solid/book/17").set({
        backgroundColor: "background-main-3"
      });
      instructionsBtn.addListener("appear", () => this.__openInstructions(), this);
      instructionsBtn.addListener("execute", () => this.__openInstructions(), this);
      header.add(instructionsBtn);

      const startBtn = this.__nodeStartButton = new qx.ui.form.Button().set({
        label: this.tr("Start"),
        icon: "@FontAwesome5Solid/play/14",
        backgroundColor: "background-main-4",
        visibility: "excluded"
      });
      header.add(startBtn);

      const stopBtn = this.__nodeStopButton = new qx.ui.form.Button().set({
        label: this.tr("Stop"),
        icon: "@FontAwesome5Solid/stop/14",
        backgroundColor: "background-main-4",
        visibility: "excluded"
      });
      header.add(stopBtn);

      const nodeStatusUI = this.__nodeStatusUI = new osparc.ui.basic.NodeStatusUI().set({
        backgroundColor: "background-main-4"
      });
      nodeStatusUI.getChildControl("label").setFont("text-14");
      header.add(nodeStatusUI);

      header.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      const outputsBtn = this._outputsBtn = new qx.ui.form.ToggleButton().set({
        width: 110,
        label: this.tr("Outputs"),
        icon: "@FontAwesome5Solid/sign-out-alt/14",
        backgroundColor: "background-main-4"
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
      const metadata = node.getMetaData();
      const serviceDetails = new osparc.info.ServiceLarge(metadata, {
        nodeId: node.getNodeId(),
        label: node.getLabel(),
        studyId: node.getStudy().getUuid()
      });
      osparc.info.ServiceLarge.popUpInWindow(serviceDetails);
    },

    __openInstructions: function() {
      if (this.getInstructionsWindow()) {
        this.getInstructionsWindow().center();
        return;
      }
      const desc = this.getNode().getSlideshowInstructions();
      if (desc) {
        const markdownInstructions = new osparc.ui.markdown.Markdown().set({
          value: desc,
          padding: 3,
          font: "text-14"
        });
        const title = this.tr("Instructions") + " - " + this.getNode().getLabel();
        const width = 600;
        const minHeight = 200;
        const win = this.__instructionsWindow = osparc.ui.window.Window.popUpInWindow(markdownInstructions, title, width, minHeight).set({
          modal: false,
          clickAwayClose: false
        });
        markdownInstructions.addListener("resized", () => win.center());

        win.getContentElement().setStyles({
          "border-color": qx.theme.manager.Color.getInstance().resolve("strong-main")
        });
        win.addListener("close", () => {
          this.__instructionsWindow = null;
          osparc.utils.Utils.makeButtonBlink(this.__instructionsBtn, 2);
        }, this);
      }
    },

    getInstructionsWindow: function() {
      return this.__instructionsWindow;
    },

    getHeaderLayout: function() {
      return this.__header;
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
      const iframe = this.getNode().getIFrame();
      if (iframe) {
        // enable/disable user interaction on iframe
        // eslint-disable-next-line no-underscore-dangle
        iframe.__iframe.getContentElement().setStyles({
          "pointer-events": enable ? "auto" : "none"
        });
      }
      if (enable) {
        if ("tapListenerId" in this._iFrameLayout) {
          this._iFrameLayout.removeListenerById(this._iFrameLayout.tapListenerId);
        }
      } else if (!this._iFrameLayout.hasListener("tap")) {
        const tapListenerId = this._iFrameLayout.addListener("tap", () => this.showPreparingInputs());
        this._iFrameLayout.tapListenerId = tapListenerId;
      }
    },

    setUpstreamDependencies: function(upstreamDependencies) {
      this.__inputsButton.setVisibility(upstreamDependencies.length > 0 ? "visible" : "hidden");
      const monitoredNodes = [];
      const workbench = this.getNode().getStudy().getWorkbench();
      upstreamDependencies.forEach(nodeId => monitoredNodes.push(workbench.getNode(nodeId)));
      this.__preparingInputs.setMonitoredNodes(monitoredNodes);
    },

    __dependenciesChanged: function() {
      const preparingNodes = this.__preparingInputs.getPreparingNodes();
      const waiting = Boolean(preparingNodes && preparingNodes.length);
      const buttonsIcon = this.__inputsButton.getChildControl("icon");
      if (waiting) {
        this.__inputsButton.setIcon("@FontAwesome5Solid/circle-notch/14");
      } else {
        this.__inputsButton.setIcon("@FontAwesome5Solid/sign-in-alt/14");
      }
      osparc.service.StatusUI.updateCircleAnimation(buttonsIcon);
      this.__enableIframeContent(!waiting);
    },

    __applyNode: function(node) {
      if (this.__nodeStatusUI) {
        this.__nodeStatusUI.setNode(node);
      }

      if (node.isDynamic()) {
        node.attachHandlersToStartButton(this.__nodeStartButton);
        osparc.utils.Utils.setIdToWidget(this.__nodeStartButton, "Start_"+node.getNodeId());
        node.attachHandlersToStopButton(this.__nodeStopButton);
      }

      this.__preparingInputs = new osparc.widget.PreparingInputs(node.getStudy());
      this.__preparingInputs.addListener("changePreparingNodes", () => this.__dependenciesChanged());
      this.__preparingInputs.addListener("startPartialPipeline", e => this.fireDataEvent("startPartialPipeline", e.getData()));
      this.__preparingInputs.addListener("stopPipeline", () => this.fireEvent("stopPipeline"));
      this.__dependenciesChanged();

      this.__instructionsBtn.setVisibility(node.getSlideshowInstructions() ? "visible" : "excluded");

      this._mainView.removeAll();
      this._addSettings();
      this._addIFrame();
      this._addOutputs();

      if (this.__progressBar) {
        const updateProgress = () => {
          const running = node.getStatus().getRunning();
          const progress = node.getStatus().getProgress();
          if (["PUBLISHED", "PENDING", "WAITING_FOR_RESOURCES", "WAITING_FOR_CLUSTER"].includes(running) ||
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
      this._outputsBtn.addListener("changeLabel", () => osparc.utils.Utils.makeButtonBlink(this._outputsBtn, 2));

      this._addLogger();
    }
  }
});
