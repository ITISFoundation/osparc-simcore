/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 *
 * -----------SimulatorActions--------------
 * -SimulatorTree--|------------------------
 * ----------------|-----RemoteRenderer-----
 * -SimulatorProps-|------------------------
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   const simulator = new qxapp.component.widget.simulator.Simulator(node);
 *   this.getRoot().add(simulator);
 * </pre>
 */

qx.Class.define("qxapp.component.widget.simulator.Simulator", {
  extend: qx.ui.core.Widget,

  /**
    * @param node {qxapp.data.model.Node} Node owning the widget
  */
  construct: function(node) {
    this.base(arguments);

    this.set({
      node: node
    });

    this._setLayout(new qx.ui.layout.VBox());

    this.__buildLayout();
    this.__initSignals();
  },

  properties: {
    node: {
      check: "qxapp.data.model.Node",
      nullable: false
    }
  },

  members: {
    __simulatorActions: null,
    __simulatorTree: null,
    __simulatorProps: null,
    __modeler: null,

    __buildLayout: function() {
      const simulatorActions = this.__simulatorActions = new qxapp.component.widget.simulator.SimulatorActions(this.getNode());
      this._add(simulatorActions);

      const splitpane = new qx.ui.splitpane.Pane("horizontal");
      splitpane.getChildControl("splitter").getChildControl("knob")
        .hide();
      splitpane.setOffset(0);

      this._add(splitpane, {
        flex: 1
      });

      const sidePanel = this.__buildSidePanel();
      splitpane.add(sidePanel);

      const modeler = this.__checkModelerIsConnected();
      if (modeler) {
        splitpane.add(modeler);
      }
    },

    __buildSidePanel: function() {
      const splitpane = new qx.ui.splitpane.Pane("vertical").set({
        width: 250,
        minWidth: 250
      });
      splitpane.getChildControl("splitter").getChildControl("knob")
        .hide();
      splitpane.setOffset(0);

      const simulatorTree = this.__buildSimulatorTree();
      const simulatorProps = this.__buildSimulatorProps();

      splitpane.add(simulatorTree);
      splitpane.add(simulatorProps);

      return splitpane;
    },

    __buildSimulatorTree: function() {
      const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox());

      const label = new qx.ui.basic.Label(this.tr("Explorer")).set({
        allowGrowX: true,
        paddingLeft: 10,
        appearance: "toolbar-textfield"
      });
      const simulatorTree = this.__simulatorTree = new qxapp.component.widget.simulator.SimulatorTree(this.getNode());

      vBox.add(label);
      vBox.add(simulatorTree, {
        flex: 1
      });

      return vBox;
    },

    __buildSimulatorProps: function() {
      const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox());

      const label = new qx.ui.basic.Label(this.tr("Properties")).set({
        allowGrowX: true,
        paddingLeft: 10,
        appearance: "toolbar-textfield"
      });
      const simulatorProps = this.__simulatorProps = new qxapp.component.widget.simulator.SimulatorProps(this.getNode());

      vBox.add(label);
      vBox.add(simulatorProps, {
        flex: 1
      });

      return vBox;
    },

    __checkModelerIsConnected: function() {
      const inputNodes = this.getNode().getInputNodes();
      for (let i=0; i<inputNodes.length; i++) {
        if (inputNodes[i].isInKey("remote-renderer")) {
          const modeler = this.__modeler = new qxapp.component.widget.RemoteRenderer(inputNodes[i], null);
          return modeler;
        }
      }
      return null;
    },

    __initSignals: function() {
      this.__simulatorTree.addListener("selectionChanged", e => {
        const selectedNode = e.getData();
        this.__simulatorActions.setContextNode(selectedNode);
        this.__simulatorProps.setContextNode(selectedNode);
      }, this);

      this.__simulatorActions.addListener("newSetting", e => {
        const data = e.getData();
        this.__simulatorTree.addConceptSetting(data.settingKey, data.itemKey);
      }, this);
    },

    checkCompatibility: function(settingKey, fromNodeKey, fromItemKey, e) {
      console.log(this.getNode().getKey(), settingKey, fromNodeKey, fromItemKey);
      let compatible = false;
      const nodeKey = this.getNode().getKey();
      if (nodeKey) {
        switch (nodeKey) {
          case "simcore/services/dynamic/itis/s4l/simulator/neuron":
            compatible = qxapp.dev.fake.neuron.Data.checkCompatibility(settingKey, fromNodeKey, fromItemKey);
            break;
          case "simcore/services/dynamic/itis/s4l/simulator/lf":
            compatible = qxapp.dev.fake.lf.Data.checkCompatibility(settingKey, fromNodeKey, fromItemKey);
            break;
        }
      }
      if (!compatible) {
        e.preventDefault();
      }
    }
  }
});
