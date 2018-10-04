const INPUTS_WIDTH = 200;

qx.Class.define("qxapp.components.widgets.SettingsView", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base();

    let hBox = new qx.ui.layout.HBox(10);
    this.set({
      layout: hBox,
      padding: 10
    });

    let inputNodesLayout = this.__inputNodesLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
    inputNodesLayout.set({
      width: INPUTS_WIDTH,
      maxWidth: INPUTS_WIDTH,
      allowGrowX: false
    });
    const navBarLabelFont = qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["nav-bar-label"]);
    let inputLabel = new qx.ui.basic.Label(this.tr("Inputs")).set({
      font: navBarLabelFont,
      alignX: "center"
    });
    inputNodesLayout.add(inputLabel);
    this.add(inputNodesLayout);


    let mainLayout = this.__mainLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
    mainLayout.set({
      alignX: "center"
    });
    this.add(mainLayout, {
      flex: 1
    });

    this.__nodesUI = [];

    this.__initTitle();
    this.__initSettings();
    this.__initButtons();
  },

  events: {
    "ShowViewer": "qx.event.type.Data"
  },

  properties: {
    workbenchModel: {
      check: "qxapp.data.model.WorkbenchModel",
      nullable: false
    },

    nodeModel: {
      check: "qxapp.data.model.NodeModel",
      apply: "__applyNode"
    }
  },

  members: {
    __settingsBox: null,
    // __dynamicViewer: null,
    __inputNodesLayout: null,
    __mainLayout: null,
    __openInteractiveNode: null,
    __openFoler: null,

    __initTitle: function() {
      let box = new qx.ui.layout.HBox();
      box.set({
        spacing: 10,
        alignX: "right"
      });
      let titleBox = new qx.ui.container.Composite(box);

      let settLabel = new qx.ui.basic.Label(this.tr("Settings"));
      settLabel.set({
        alignX: "center",
        alignY: "middle"
      });

      titleBox.add(settLabel, {
        width: "75%"
      });
      this.__mainLayout.add(titleBox);
    },

    __initSettings: function() {
      this.__settingsBox = new qx.ui.container.Composite(new qx.ui.layout.Grow());
      this.__mainLayout.add(this.__settingsBox);

      // this.__dynamicViewer = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
      // this.add(this.__dynamicViewer);
    },

    __initButtons: function() {
      let box = new qx.ui.layout.HBox();
      box.set({
        spacing: 10,
        alignX: "right"
      });
      let buttonsBox = new qx.ui.container.Composite(box);

      let openInteractiveNode = this.__openInteractiveNode = new qx.ui.form.Button().set({
        icon: "@FontAwesome5Solid/play/32"
      });

      let openFolder = this.__openFoler = new qx.ui.form.Button().set({
        icon: "@FontAwesome5Solid/folder-open/32"
      });

      buttonsBox.add(openInteractiveNode);
      buttonsBox.add(openFolder);
      this.__mainLayout.add(buttonsBox);
    },

    __applyNode: function(nodeModel, oldNode, propertyName) {
      this.__settingsBox.removeAll();
      this.__settingsBox.add(nodeModel.getPropsWidget());

      /*
      this.__dynamicViewer.removeAll();
      let viewerButton = nodeModel.getViewerButton();
      if (viewerButton) {
        nodeModel.addListenerOnce("ShowViewer", function(e) {
          const data = e.getData();
          this.fireDataEvent("ShowViewer", data);
        }, this);
        this.__dynamicViewer.add(viewerButton);
      }
      */
    }
  }
});
