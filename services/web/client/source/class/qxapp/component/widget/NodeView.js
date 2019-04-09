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
 *   nodeView.setNode(workbench.getNode1());
 *   this.getRoot().add(nodeView);
 * </pre>
 */

qx.Class.define("qxapp.component.widget.NodeView", {
  extend: qx.ui.splitpane.Pane,

  construct: function() {
    this.base(arguments);

    const inputNodesLayout = this.__inputNodesLayout = new qxapp.desktop.SidePanel();
    const navBarLabelFont = qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["nav-bar-label"]);
    let inputLabel = new qx.ui.basic.Label(this.tr("Inputs")).set({
      font: navBarLabelFont,
      alignX: "center"
    });
    inputNodesLayout.add(inputLabel);

    const scroll = new qx.ui.container.Scroll().set({
      minWidth: 0
    });
    scroll.add(inputNodesLayout);
    this.add(scroll, 0);

    const mainLayout = this.__mainLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
      alignX: "center",
      padding: [0, 10]
    });

    this.add(mainLayout, 1);

    this.__attachEventHandlers();
  },

  properties: {
    node: {
      check: "qxapp.data.model.Node",
      apply: "_rebuildLayout"
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

    _rebuildLayout: function() {
      this.__addInputPortsUIs();

      this.__mainLayout.removeAll();
      if (this.getNode().isInKey("s4l/simulator")) {
        let widget = new qxapp.component.widget.simulator.Simulator(this.getNode());
        console.log(widget);
        this.__mainLayout.add(widget, {
          flex: 1
        });
        this.__inputNodesLayout.set({
          width: 200
        });
      } else {
        this.__addSettings();
        this.__addMapper();
        this.__addIFrame();
        this.__addButtons();

        this.__initIFrame();
        this.__initButtons();
      }
    },

    hasIFrame: function() {
      return (this.isPropertyInitialized("node") && this.getNode().getIFrame());
    },

    restoreIFrame: function() {
      if (this.hasIFrame()) {
        const iFrame = this.getNode().getIFrame();
        if (iFrame) {
          iFrame.maximizeIFrame(false);
        }
      }
    },

    __addInputPortsUIs: function() {
      this.__clearInputPortsUIs();

      // Add the default inputs if any
      if (Object.keys(this.getNode().getInputsDefault()).length > 0) {
        this.__createInputPortsUI(this.getNode(), false);
      }

      // Add the representations for the inputs
      const inputNodes = this.getNode().getInputNodes();
      for (let i=0; i<inputNodes.length; i++) {
        let inputNode = inputNodes[i];
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

    __createInputPortsUI: function(inputNode, isInputModel = true) {
      let nodePorts = null;
      if (isInputModel) {
        nodePorts = inputNode.getOutputWidget();
      } else {
        nodePorts = inputNode.getInputsDefaultWidget();
      }
      if (nodePorts) {
        this.__inputNodesLayout.add(nodePorts);
      }
      return nodePorts;
    },

    __addSettings: function() {
      if (!this.__settingsLayout) {
        this.__settingsLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(18));
      }
      this.__settingsLayout.removeAll();

      const propsWidget = this.getNode().getPropsWidget();
      if (propsWidget) {
        let box = new qx.ui.layout.HBox();
        box.set({
          spacing: 10,
          alignX: "center"
        });
        let titleBox = new qx.ui.container.Composite(box);
        let settLabel = new qx.ui.basic.Label(this.tr("Settings")).set({
          font: "nav-bar-label"
        });
        titleBox.add(settLabel);

        this.__settingsLayout.add(titleBox);
        this.__settingsLayout.add(propsWidget);

        this.__mainLayout.add(this.__settingsLayout);
      } else if (qx.ui.core.Widget.contains(this.__mainLayout, this.__settingsLayout)) {
        this.__mainLayout.remove(this.__settingsLayout);
      }
    },

    __addMapper: function() {
      if (!this.__mapperLayout) {
        this.__mapperLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
      }
      this.__mapperLayout.removeAll();

      const mapper = this.getNode().getInputsMapper();
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

    __addIFrame: function() {
      if (!this.__iFrameLayout) {
        this.__iFrameLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
      }
      this.__iFrameLayout.removeAll();

      const iFrame = this.getNode().getIFrame();
      if (iFrame) {
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

    __addButtons: function() {
      if (!this.__buttonsLayout) {
        let box = new qx.ui.layout.HBox();
        box.set({
          spacing: 10,
          alignX: "right"
        });
        this.__buttonsLayout = new qx.ui.container.Composite(box);
      }
      this.__buttonsLayout.removeAll();

      let retrieveIFrameButton = this.getNode().getRetrieveIFrameButton();
      if (retrieveIFrameButton) {
        this.__buttonsLayout.add(retrieveIFrameButton);
      }
      let restartIFrameButton = this.getNode().getRestartIFrameButton();
      if (restartIFrameButton) {
        this.__buttonsLayout.add(restartIFrameButton);
      }
      let openFolder = this.__openFolder = new qx.ui.form.Button().set({
        icon: "@FontAwesome5Solid/folder-open/32"
      });
      this.__buttonsLayout.add(openFolder);
      this.__mainLayout.add(this.__buttonsLayout);
    },

    __initIFrame: function() {
      const iFrame = this.getNode().getIFrame();
      if (iFrame) {
        iFrame.addListener("maximize", e => {
          this.__maximizeIFrame(true);
        }, this);
        iFrame.addListener("restore", e => {
          this.__maximizeIFrame(false);
        }, this);
        this.__maximizeIFrame(iFrame.hasState("maximized"));
      }
    },

    __initButtons: function() {
      if (this.__openFolder) {
        this.__openFolder.addListener("execute", function() {
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
      }
    },

    __maximizeIFrame: function(maximize) {
      const othersStatus = maximize ? "excluded" : "visible";
      this.__inputNodesLayout.setVisibility(othersStatus);
      this.__settingsLayout.setVisibility(othersStatus);
      this.__mapperLayout.setVisibility(othersStatus);
      this.__buttonsLayout.setVisibility(othersStatus);
    },

    __attachEventHandlers: function() {
      this.__blocker.addListener("tap", this.__inputNodesLayout.toggleCollapsed.bind(this.__inputNodesLayout));
    }
  }
});
