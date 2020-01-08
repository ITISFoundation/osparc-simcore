/* ************************************************************************

   osparc - the simcore frontend

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
 *   let nodeView = new osparc.component.widget.NodeView();
 *   nodeView.setWorkbench(workbench);
 *   nodeView.setNode(workbench.getNode1());
 *   nodeView.buildLayout();
 *   this.getRoot().add(nodeView);
 * </pre>
 */

qx.Class.define("osparc.component.widget.NodeView", {
  extend: qx.ui.splitpane.Pane,

  construct: function() {
    this.base(arguments);

    const inputPanel = this.__inputPanel = new osparc.desktop.SidePanel().set({
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
    const collapseBtn = this.__collapseBtn = new qx.ui.toolbar.Button(this.tr("Collapse all"), "@FontAwesome5Solid/minus-square/14");
    buttonPart.add(collapseBtn);
    inputPanel.add(titleBar);

    const scroll = this.__scrollContainer = new qx.ui.container.Scroll();
    const inputContainer = this.__inputNodesLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox());
    scroll.add(inputContainer);
    inputPanel.add(scroll, {
      flex: 1
    });

    this.add(inputPanel, 0);

    const mainLayout = this.__mainLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
    this.add(mainLayout, 1);

    this.__settingsLayout = new qx.ui.groupbox.GroupBox(this.tr("Settings")).set({
      appearance: "settings-groupbox",
      maxWidth: 500,
      alignX: "center"
    });
    this.__settingsLayout.setLayout(new qx.ui.layout.VBox());
    this.__mapperLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
    this.__iFrameLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox());

    mainLayout.add(this.__initToolbar());

    this.__attachEventHandlers();
  },

  properties: {
    workbench: {
      check: "osparc.data.model.Workbench",
      nullable: false
    },

    node: {
      check: "osparc.data.model.Node",
      apply: "_applyNode"
    }
  },

  members: {
    __mainLayout: null,
    __scrollContainer: null,
    __inputPanel: null,
    __inputNodesLayout: null,
    __settingsLayout: null,
    __mapperLayout: null,
    __iFrameLayout: null,
    __toolbar: null,
    __title: null,
    __buttonContainer: null,
    __filesButton: null,
    __collapseBtn: null,

    __initToolbar: function() {
      const toolbar = this.__toolbar = new qx.ui.toolbar.ToolBar();
      const titlePart = new qx.ui.toolbar.Part();
      const infoPart = new qx.ui.toolbar.Part();
      const buttonsPart = this.__buttonContainer = new qx.ui.toolbar.Part();
      toolbar.add(titlePart);
      toolbar.add(infoPart);
      toolbar.addSpacer();

      const title = this.__title = new osparc.ui.form.EditLabel().set({
        labelFont: "title-18",
        inputFont: "text-18"
      });
      titlePart.add(title);

      const infoBtn = new qx.ui.toolbar.Button(this.tr("Info"), "@FontAwesome5Solid/info-circle/14");
      infoPart.add(infoBtn);

      const filesBtn = this.__filesButton = new qx.ui.toolbar.Button(this.tr("Files"), "@FontAwesome5Solid/folder-open/14");
      osparc.utils.Utils.setIdToWidget(filesBtn, "nodeViewFilesBtn");
      buttonsPart.add(filesBtn);

      filesBtn.addListener("execute", () => this.__openNodeDataManager(), this);

      infoBtn.addListener("execute", () => this.__openServiceInfo(), this);

      title.addListener("editValue", evt => {
        if (evt.getData() !== this.__title.getValue()) {
          const node = this.getNode();
          if (node) {
            node.renameNode(evt.getData());
          }
          qx.event.message.Bus.getInstance().dispatchByName(
            "updateStudy",
            this.getWorkbench().getStudy()
              .serializeStudy()
          );
        }
      }, this);

      return toolbar;
    },

    buildLayout: function() {
      this.__addInputPortsUIs();
      this.__addSettings();
      this.__addMapper();
      this.__addIFrame();
      this.__addButtons();
    },

    __addInputPortsUIs: function() {
      this.__inputNodesLayout.removeAll();

      // Add the default inputs if any
      if (Object.keys(this.getNode().getInputsDefault()).length > 0) {
        this.__createInputPortsUI(this.getNode(), false);
      }

      // Add the representations for the inputs
      const inputNodes = this.getNode().getInputNodes();
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
      nodePorts.setCollapsed(false);
      return nodePorts;
    },

    __addSettings: function() {
      const propsWidget = this.getNode().getPropsWidget();
      this.__settingsLayout.removeAll();
      if (propsWidget && Object.keys(this.getNode().getInputs()).length) {
        this.__settingsLayout.add(propsWidget);
        this.__mainLayout.add(this.__settingsLayout);
      } else if (qx.ui.core.Widget.contains(this.__mainLayout, this.__settingsLayout)) {
        this.__mainLayout.remove(this.__settingsLayout);
      }
    },

    __addMapper: function() {
      const mapper = this.getNode().getInputsMapper();
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

    __addIFrame: function() {
      const iFrame = this.getNode().getIFrame();
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
      this.__toolbar.setVisibility(othersStatus);
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

    __addButtons: function() {
      this.__buttonContainer.removeAll();
      let retrieveIFrameButton = this.getNode().getRetrieveIFrameButton();
      if (retrieveIFrameButton) {
        this.__buttonContainer.add(retrieveIFrameButton);
      }
      let restartIFrameButton = this.getNode().getRestartIFrameButton();
      if (restartIFrameButton) {
        this.__buttonContainer.add(restartIFrameButton);
      }
      this.__buttonContainer.add(this.__filesButton);
      this.__toolbar.add(this.__buttonContainer);
    },

    __openNodeDataManager: function() {
      const nodeDataManager = new osparc.component.widget.NodeDataManager(this.getNode());

      const win = new qx.ui.window.Window(this.getNode().getLabel()).set({
        appearance: "service-window",
        layout: new qx.ui.layout.Grow(),
        autoDestroy: true,
        contentPadding: 0,
        height: 600,
        modal: true,
        showMinimize: false,
        width: 900
      });
      const closeBtn = win.getChildControl("close-button");
      osparc.utils.Utils.setIdToWidget(closeBtn, "nodeDataManagerCloseBtn");
      win.add(nodeDataManager);

      win.center();
      win.open();
    },

    __openServiceInfo: function() {
      const win = new osparc.component.metadata.ServiceInfoWindow(this.getNode().getMetaData());
      win.center();
      win.open();
    },

    __attachEventHandlers: function() {
      this.__blocker.addListener("tap", this.__inputPanel.toggleCollapsed.bind(this.__inputPanel));

      const maximizeIframeCb = msg => {
        this.__blocker.setStyles({
          display: msg.getData() ? "none" : "block"
        });
        this.__inputPanel.setVisibility(msg.getData() ? "excluded" : "visible");
      };

      this.addListener("appear", () => {
        qx.event.message.Bus.getInstance().subscribe("maximizeIframe", maximizeIframeCb, this);
      }, this);

      this.addListener("disappear", () => {
        qx.event.message.Bus.getInstance().unsubscribe("maximizeIframe", maximizeIframeCb, this);
      }, this);

      this.__collapseBtn.addListener("execute", () => {
        this.__inputNodesLayout.getChildren().forEach(node => {
          node.setCollapsed(true);
        });
      }, this);
    },

    _applyNode: function(node) {
      node.bind("label", this.__title, "value");
    }
  }
});
