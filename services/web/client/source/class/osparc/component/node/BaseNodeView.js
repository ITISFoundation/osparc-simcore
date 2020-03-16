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
    _title: null,
    _toolbar: null,
    _mainView: null,
    _inputsView: null,
    _inputNodesLayout: null,
    _collapseBtn: null,
    _settingsLayout: null,
    _mapperLayout: null,
    _iFrameLayout: null,
    _buttonContainer: null,
    _filesButton: null,

    populateLayout: function() {
      this.getNode().bind("label", this._title, "value");
      this._addInputPortsUIs();
      this._addSettings();
      this._addIFrame();
      this._addButtons();
    },

    __buildInputsView: function() {
      const inputsView = this._inputsView = new osparc.desktop.SidePanel().set({
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
      const collapseBtn = this._collapseBtn = new qx.ui.toolbar.Button(this.tr("Collapse all"), "@FontAwesome5Solid/minus-square/14");
      buttonPart.add(collapseBtn);
      inputsView.add(titleBar);

      const scroll = new qx.ui.container.Scroll();
      const inputContainer = this._inputNodesLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      scroll.add(inputContainer);
      inputsView.add(scroll, {
        flex: 1
      });

      this.add(inputsView, 0);
    },

    __buildMainView: function() {
      const mainView = this._mainView = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
      this.add(mainView, 1);

      this._settingsLayout = this.self().createSettingsGroupBox(this.tr("Settings"));
      this._mapperLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
      this._iFrameLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox());

      mainView.add(this.__buildToolbar());
    },

    __buildLayout: function() {
      this.__buildInputsView();
      this.__buildMainView();
    },

    __buildToolbar: function() {
      const toolbar = this._toolbar = new qx.ui.toolbar.ToolBar();
      const titlePart = new qx.ui.toolbar.Part();
      const infoPart = new qx.ui.toolbar.Part();
      const buttonsPart = this._buttonContainer = new qx.ui.toolbar.Part();
      toolbar.add(titlePart);
      toolbar.add(infoPart);
      toolbar.addSpacer();

      const title = this._title = new osparc.ui.form.EditLabel().set({
        labelFont: "title-18",
        inputFont: "text-18",
        editable: osparc.data.Permissions.getInstance().canDo("study.node.rename")
      });
      title.addListener("editValue", evt => {
        if (evt.getData() !== this._title.getValue()) {
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

      const filesBtn = this._filesButton = new qx.ui.toolbar.Button(this.tr("Files"), "@FontAwesome5Solid/folder-open/14");
      osparc.utils.Utils.setIdToWidget(filesBtn, "nodeViewFilesBtn");
      filesBtn.addListener("execute", () => this.__openNodeDataManager(), this);
      buttonsPart.add(filesBtn);

      return toolbar;
    },

    _addToMainView: function(view, options = {}) {
      if (view.hasChildren()) {
        this._mainView.add(view, options);
      } else if (qx.ui.core.Widget.contains(this._mainView, view)) {
        this._mainView.remove(view);
      }
    },

    _addInputPortsUIs: function() {
      this._inputNodesLayout.removeAll();

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
        this._inputNodesLayout.add(nodePorts, {
          flex: 1
        });
        nodePorts.setCollapsed(false);
      }
    },

    _addButtons: function() {
      this._buttonContainer.removeAll();
      let retrieveIFrameButton = this.getNode().getRetrieveIFrameButton();
      if (retrieveIFrameButton) {
        this._buttonContainer.add(retrieveIFrameButton);
      }
      this._buttonContainer.add(this._filesButton);
      this._toolbar.add(this._buttonContainer);
    },

    _maximizeIFrame: function(maximize) {
      const othersStatus = maximize ? "excluded" : "visible";
      this._inputNodesLayout.setVisibility(othersStatus);
      this._settingsLayout.setVisibility(othersStatus);
      this._mapperLayout.setVisibility(othersStatus);
      this._toolbar.setVisibility(othersStatus);
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
      this.__blocker.addListener("tap", this._inputsView.toggleCollapsed.bind(this._inputsView));

      const maximizeIframeCb = msg => {
        this.__blocker.setStyles({
          display: msg.getData() ? "none" : "block"
        });
        this._inputsView.setVisibility(msg.getData() ? "excluded" : "visible");
      };

      this.addListener("appear", () => {
        qx.event.message.Bus.getInstance().subscribe("maximizeIframe", maximizeIframeCb, this);
      }, this);

      this.addListener("disappear", () => {
        qx.event.message.Bus.getInstance().unsubscribe("maximizeIframe", maximizeIframeCb, this);
      }, this);

      this._collapseBtn.addListener("execute", () => {
        this._inputNodesLayout.getChildren().forEach(node => {
          node.setCollapsed(true);
        });
      }, this);
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
