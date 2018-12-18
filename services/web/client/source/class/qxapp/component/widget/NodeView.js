/* ************************************************************************
   Copyright: 2018 ITIS Foundation
   License:   MIT
   Authors:   Odei Maiz <maiz@itis.swiss>
   Utf8Check: äöü
************************************************************************ */

/**
 *  Node Main view
 * - On the left side shows the default inputs if any and also what the input nodes offer
 * - In the center the content of the node: settings, mapper, iframe...
 */

const PORT_INPUTS_WIDTH = 300;

qx.Class.define("qxapp.component.widget.NodeView", {
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
      width: PORT_INPUTS_WIDTH,
      maxWidth: PORT_INPUTS_WIDTH,
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
      alignX: "center",
      padding: 5
    });
    this.add(mainLayout, {
      flex: 1
    });

    this.__settingsLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
    this.__mapperLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
    this.__iFrameLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
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
    __mainLayout: null,
    __inputNodesLayout: null,
    __settingsLayout: null,
    __mapperLayout: null,
    __iFrameLayout: null,
    __buttonsLayout: null,
    __openFolder: null,

    __initButtons: function() {
      let box = new qx.ui.layout.HBox();
      box.set({
        spacing: 10,
        alignX: "right"
      });
      let buttonsLayout = this.__buttonsLayout = new qx.ui.container.Composite(box);

      let openFolder = this.__openFolder = new qx.ui.form.Button().set({
        icon: "@FontAwesome5Solid/folder-open/32"
      });
      openFolder.addListener("execute", function() {
        let fileManager = new qxapp.component.widget.FileManager(this.getNodeModel());

        let win = new qx.ui.window.Window(this.getNodeModel().getLabel()).set({
          layout: new qx.ui.layout.Canvas(),
          contentPadding: 0,
          showMinimize: false,
          width: 900,
          height: 600
        });
        win.add(fileManager, {
          top: 0,
          right: 0,
          bottom: 0,
          left: 0
        });

        win.center();
        win.open();
      }, this);

      buttonsLayout.add(openFolder);
    },

    __createInputPortsUI: function(inputNodeModel, isInputModel = true) {
      let nodePorts = null;
      if (isInputModel) {
        nodePorts = inputNodeModel.getOutputWidget();
      } else {
        nodePorts = inputNodeModel.getInputsDefaultWidget();
      }
      if (nodePorts) {
        this.__inputNodesLayout.add(nodePorts, {
          flex: 1
        });
      }
      return nodePorts;
    },

    __addInputPortsUIs: function(nodeModel) {
      this.__clearInputPortsUIs();

      // Add the default inputs if any
      if (Object.keys(this.getNodeModel().getInputsDefault()).length > 0) {
        this.__createInputPortsUI(this.getNodeModel(), false);
      }

      // Add the representations for the inputs
      const inputNodes = nodeModel.getInputNodes();
      for (let i=0; i<inputNodes.length; i++) {
        let inputNodeModel = this.getWorkbenchModel().getNodeModel(inputNodes[i]);
        if (inputNodeModel.isContainer()) {
          for (const exposedInnerNodeId in inputNodeModel.getExposedInnerNodes()) {
            const exposedInnerNode = inputNodeModel.getExposedInnerNodes()[exposedInnerNodeId];
            this.__createInputPortsUI(exposedInnerNode);
          }
        } else {
          this.__createInputPortsUI(inputNodeModel);
        }
      }
    },

    __clearInputPortsUIs: function() {
      // remove all but the title
      while (this.__inputNodesLayout.getChildren().length > 1) {
        this.__inputNodesLayout.removeAt(this.__inputNodesLayout.getChildren().length-1);
      }
    },

    __addSettings: function(propsWidget) {
      this.__settingsLayout.removeAll();
      if (propsWidget) {
        let box = new qx.ui.layout.HBox();
        box.set({
          spacing: 10,
          alignX: "right"
        });
        let titleBox = new qx.ui.container.Composite(box);
        let settLabel = new qx.ui.basic.Label(this.tr("Settings"));
        settLabel.set({
          alignX: "center"
        });
        titleBox.add(settLabel, {
          width: "75%"
        });

        this.__settingsLayout.add(titleBox);
        this.__settingsLayout.add(propsWidget);

        this.__mainLayout.add(this.__settingsLayout);
      } else if (qx.ui.core.Widget.contains(this.__mainLayout, this.__settingsLayout)) {
        this.__mainLayout.remove(this.__settingsLayout);
      }
    },

    __addMapper: function(mapper) {
      this.__mapperLayout.removeAll();
      if (mapper) {
        this.__mapperLayout.add(mapper, {
          flex: 1
        });
        this.__mainLayout.add(this.__mapperLayout, {
          flex: 1
        });
      } else if (qx.ui.core.Widget.contains(this.__mainLayout, this.__mapperLayout)) {
        this.__mainLayout.remove(this.__mapperLayout);
      }
    },

    __addIFrame: function(iFrame) {
      this.__iFrameLayout.removeAll();
      if (iFrame) {
        iFrame.addListener("maximize", e => {
          this.__maximizeIFrame(true);
        }, this);
        iFrame.addListener("restore", e => {
          this.__maximizeIFrame(false);
        }, this);
        this.__maximizeIFrame(iFrame.hasState("maximized"));
        this.__iFrameLayout.add(iFrame, {
          flex: 1
        });
        this.__mainLayout.add(this.__iFrameLayout, {
          flex: 1
        });
      } else if (qx.ui.core.Widget.contains(this.__mainLayout, this.__iFrameLayout)) {
        this.__mainLayout.remove(this.__iFrameLayout);
      }
    },

    __maximizeIFrame: function(maximize) {
      const othersStatus = maximize ? "excluded" : "visible";
      this.__inputNodesLayout.setVisibility(othersStatus);
      this.__settingsLayout.setVisibility(othersStatus);
      this.__mapperLayout.setVisibility(othersStatus);
      this.__buttonsLayout.setVisibility(othersStatus);
    },

    __addButtons: function(nodeModel) {
      this.__buttonsLayout.removeAll();
      let retrieveIFrameButton = nodeModel.getRetrieveIFrameButton();
      if (retrieveIFrameButton) {
        this.__buttonsLayout.add(retrieveIFrameButton);
      }
      let restartIFrameButton = nodeModel.getRestartIFrameButton();
      if (restartIFrameButton) {
        this.__buttonsLayout.add(restartIFrameButton);
      }
      this.__buttonsLayout.add(this.__openFolder);
      this.__mainLayout.add(this.__buttonsLayout);
    },

    __applyNode: function(nodeModel, oldNode, propertyName) {
      this.__addInputPortsUIs(nodeModel);
      this.__addSettings(nodeModel.getPropsWidget());
      this.__addMapper(nodeModel.getInputsMapper());
      this.__addIFrame(nodeModel.getIFrame());
      this.__addButtons(nodeModel);
    }
  }
});
