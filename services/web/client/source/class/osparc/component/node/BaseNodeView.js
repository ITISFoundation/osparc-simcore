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
      apply: "__applyNode",
      nullable: true,
      init: null
    }
  },

  members: {
    __header: null,
    __nodeStatusUI: null,
    __retrieveButton: null,
    _mainView: null,
    _settingsLayout: null,
    _iFrameLayout: null,
    _outputsLayout: null,

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

    __buildHeader: function() {
      const header = this.__header = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
        alignX: "center"
      })).set({
        height: this.self().HEADER_HEIGHT
      });

      const infoBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/info-circle/14");
      infoBtn.addListener("execute", () => this.__openServiceDetails(), this);
      header.add(infoBtn);

      header.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      const nodeStatusUI = this.__nodeStatusUI = new osparc.ui.basic.NodeStatusUI();
      nodeStatusUI.getChildControl("label").setFont("text-14");
      header.add(nodeStatusUI);

      const retrieveBtn = this.__retrieveButton = new qx.ui.form.Button(this.tr("Retrieve"), "@FontAwesome5Solid/spinner/14");
      retrieveBtn.addListener("execute", () => this.getNode().callRetrieveInputs(), this);
      header.add(retrieveBtn);

      header.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      const outputsBtn = this._outputsBtn = new qx.ui.form.ToggleButton(this.tr("Outputs"), "@FontAwesome5Solid/sign-out-alt/14");
      header.add(outputsBtn);

      return header;
    },

    __buildMainView: function() {
      const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));

      const mainView = this._mainView = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      const groupBox = this._settingsLayout = this.self().createSettingsGroupBox(this.tr("Settings"));
      this.bind("backgroundColor", groupBox, "backgroundColor");
      this.bind("backgroundColor", groupBox.getChildControl("frame"), "backgroundColor");

      this._iFrameLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox());

      hBox.add(mainView, {
        flex: 1
      });

      const outputsLayout = this._outputsLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
        padding: 5,
        width: 250
      });
      this._outputsBtn.bind("value", outputsLayout, "visibility", {
        converter: value => value ? "visible" : "excluded"
      });
      hBox.add(outputsLayout);

      return hBox;
    },

    _addToMainView: function(view, options = {}) {
      if (view.hasChildren()) {
        this._mainView.add(view, options);
      } else if (qx.ui.core.Widget.contains(this._mainView, view)) {
        this._mainView.remove(view);
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
      this.__nodeStatusUI.setNode(node);
      this.__retrieveButton.setVisibility(this.getNode().isDynamic() ? "visible" : "excluded");

      this._mainView.removeAll();
      this._addSettings();
      this._addIFrame();

      this._addOutputs();

      this._addLogger();
    }
  }
});
