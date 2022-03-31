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
        layout: new qx.ui.layout.VBox()
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
    __nodeStatusUI: null,
    __retrieveButton: null,
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
      const header = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
        alignX: "center"
      })).set({
        padding: 6,
        height: this.self().HEADER_HEIGHT
      });

      const infoBtn = new qx.ui.form.Button(null, "@MaterialIcons/info_outline/16").set({
        backgroundColor: "transparent",
        toolTipText: this.tr("Information")
      });
      infoBtn.addListener("execute", () => this.__openServiceDetails(), this);
      header.add(infoBtn);

      header.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      const nodeStatusUI = this.__nodeStatusUI = new osparc.ui.basic.NodeStatusUI().set({
        backgroundColor: "background-main-4"
      });
      nodeStatusUI.getChildControl("label").setFont("text-14");
      header.add(nodeStatusUI);

      const retrieveBtn = this.__retrieveButton = new qx.ui.form.Button(null, "@FontAwesome5Solid/spinner/14").set({
        backgroundColor: "transparent",
        toolTipText: this.tr("Retrieve")
      });
      retrieveBtn.addListener("execute", () => this.getNode().callRetrieveInputs(), this);
      header.add(retrieveBtn);

      header.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      const outputsBtn = this._outputsBtn = new qx.ui.form.ToggleButton(null, "@FontAwesome5Solid/sign-out-alt/14").set({
        backgroundColor: "transparent",
        toolTipText: this.tr("Outputs")
      });
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

      const outputsLayout = this._outputsLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
        padding: 5,
        width: 250
      });
      mainView.bind("backgroundColor", outputsLayout, "backgroundColor");
      this._outputsBtn.bind("value", outputsLayout, "visibility", {
        converter: value => value ? "visible" : "excluded"
      });
      hBox.add(outputsLayout);

      return hBox;
    },

    __openNodeDataManager: function() {
      this.self().openNodeDataManager(this.getNode());
    },

    __openServiceDetails: function() {
      const serviceDetails = new osparc.servicecard.Large(this.getNode().getMetaData(), this.getNode().getNodeId());
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

    __applyNode: function(node) {
      if (this.__nodeStatusUI) {
        this.__nodeStatusUI.setNode(node);
      }

      if (this.__retrieveButton) {
        this.__retrieveButton.setVisibility(node.isDynamic() ? "visible" : "excluded");
      }

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

      this._addLogger();
    }
  }
});
