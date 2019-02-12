/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget that displays the main view of a node.
 * - On the left side shows the default inputs if any and also what the input nodes offer
 * - In the center the content of the node: settings, mapper, iframe...
 *
 * When a node is set the layout is built
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let nodeView = new qxapp.component.widget.NodeView();
 *   nodeView.setWorkbench(workbench);
 *   nodeView.setNode(workbench.getNode1());
 *   this.getRoot().add(nodeView);
 * </pre>
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

  properties: {
    workbench: {
      check: "qxapp.data.model.Workbench",
      nullable: false
    },

    node: {
      check: "qxapp.data.model.Node",
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
        let nodeDataManager = new qxapp.component.widget.NodeDataManager(this.getNode());

        let win = new qx.ui.window.Window(this.getNode().getLabel()).set({
          layout: new qx.ui.layout.Canvas(),
          contentPadding: 0,
          showMinimize: false,
          width: 900,
          height: 600
        });
        win.add(nodeDataManager, {
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

    __createInputPortsUI: function(inputNode, isInputModel = true) {
      let nodePorts = null;
      if (isInputModel) {
        nodePorts = inputNode.getOutputWidget();
      } else {
        nodePorts = inputNode.getInputsDefaultWidget();
      }
      if (nodePorts) {
        this.__inputNodesLayout.add(nodePorts, {
          flex: 1
        });
      }
      return nodePorts;
    },

    __addInputPortsUIs: function(node) {
      this.__clearInputPortsUIs();

      // Add the default inputs if any
      if (Object.keys(this.getNode().getInputsDefault()).length > 0) {
        this.__createInputPortsUI(this.getNode(), false);
      }

      // Add the representations for the inputs
      const inputNodes = node.getInputNodes();
      for (let i=0; i<inputNodes.length; i++) {
        let inputNode = this.getWorkbench().getNode(inputNodes[i]);
        if (inputNode.isContainer()) {
          for (const exposedInnerNodeId in inputNode.getExposedInnerNodes()) {
            const exposedInnerNode = inputNode.getExposedInnerNodes()[exposedInnerNodeId];
            this.__createInputPortsUI(exposedInnerNode);
          }
        } else {
          this.__createInputPortsUI(inputNode);
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

    __addButtons: function(node) {
      this.__buttonsLayout.removeAll();
      let retrieveIFrameButton = node.getRetrieveIFrameButton();
      if (retrieveIFrameButton) {
        this.__buttonsLayout.add(retrieveIFrameButton);
      }
      let restartIFrameButton = node.getRestartIFrameButton();
      if (restartIFrameButton) {
        this.__buttonsLayout.add(restartIFrameButton);
      }
      this.__buttonsLayout.add(this.__openFolder);
      this.__mainLayout.add(this.__buttonsLayout);
    },

    __applyNode: function(node, oldNode, propertyName) {
      this.__addInputPortsUIs(node);
      this.__addSettings(node.getPropsWidget());
      this.__addMapper(node.getInputsMapper());
      this.__addIFrame(node.getIFrame());
      this.__addButtons(node);
    }
  }
});
