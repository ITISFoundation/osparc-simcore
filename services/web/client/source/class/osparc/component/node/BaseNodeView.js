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
      apply: "_applyNode",
      nullable: true,
      init: null
    }
  },

  members: {
    __serviceInfoLayout: null,
    __nodeStatusUI: null,
    __header: null,
    _mainView: null,
    _settingsLayout: null,
    _iFrameLayout: null,
    __buttonContainer: null,
    __outFilesButton: null,

    populateLayout: function() {
      this._addButtons();

      this._mainView.removeAll();
      this._addSettings();
      this._addIFrame();

      this._addLogger();
    },

    __buildLayout: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
      const header = this.__buildHeader();
      layout.add(header);

      const mainView = this.__buildMainView();
      layout.add(mainView, {
        flex: 1
      });

      this.add(layout, 1);
    },

    __buildMainView: function() {
      const mainView = this._mainView = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      const groupBox = this._settingsLayout = this.self().createSettingsGroupBox(this.tr("Settings"));
      this.bind("backgroundColor", groupBox, "backgroundColor");
      this.bind("backgroundColor", groupBox.getChildControl("frame"), "backgroundColor");

      this._iFrameLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox());

      return mainView;
    },

    __buildHeader: function() {
      const header = this.__header = new qx.ui.container.Composite(new qx.ui.layout.HBox(20).set({
        alignX: "center"
      })).set({
        height: this.self().HEADER_HEIGHT
      });

      const infoLayout = this.__serviceInfoLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      header.add(infoLayout);

      // just a placeholder until the node is set
      const nodeStatusUI = this.__nodeStatusUI = new qx.ui.core.Widget();
      header.add(nodeStatusUI);

      const buttonsLayout = this.__buttonContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      const filesBtn = this.__outFilesButton = new qx.ui.form.Button(this.tr("Outputs"), "@FontAwesome5Solid/sign-out-alt/14");
      osparc.utils.Utils.setIdToWidget(filesBtn, "nodeOutputFilesBtn");
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
      this.self().openNodeDataManager(this.getNode());
    },

    __openServiceDetails: function() {
      const serviceDetails = new osparc.servicecard.Large(this.getNode().getMetaData());
      const title = this.tr("Service information");
      const width = 600;
      const height = 700;
      osparc.ui.window.Window.popUpInWindow(serviceDetails, title, width, height);
    },

    getHeaderLayout: function() {
      return this.__header;
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
