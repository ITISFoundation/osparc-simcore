/* global qxapp */

qx.Class.define("qxapp.components.workbench.NodeBase", {
  extend: qx.ui.window.Window,

  construct: function(metadata) {
    this.base();

    this.set({
      showMinimize: false,
      showMaximize: false,
      showClose: false,
      showStatusbar: false,
      resizable: false,
      allowMaximize: false,
      minWidth: 180
    });

    this.setNodeId(qxapp.utils.Utils.uuidv4());

    let nodeLayout = new qx.ui.layout.VBox(5, null, "separator-vertical");
    this.setLayout(nodeLayout);

    let inputsOutputsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(20));
    this.add(inputsOutputsLayout, {flex: 1});

    let inputsBox = new qx.ui.layout.VBox(5);
    inputsBox.setAlignX("left");
    this._inputPorts = new qx.ui.container.Composite(inputsBox);
    inputsOutputsLayout.add(this._inputPorts, {width: "50%"});

    let outputsBox = new qx.ui.layout.VBox(5);
    outputsBox.setAlignX("right");
    this._outputPorts = new qx.ui.container.Composite(outputsBox);
    inputsOutputsLayout.add(this._outputPorts, {width: "50%"});

    let progressBox = new qx.ui.layout.HBox(5);
    progressBox.setAlignX("center");
    let progressLayout = new qx.ui.container.Composite(progressBox);
    this._progressLabel = new qx.ui.basic.Label("0%");
    progressLayout.add(this._progressLabel);
    this.add(progressLayout);

    this._inputLinkIDs = [];
    this._outputLinkIDs = [];

    if (metadata != undefined) {
      this._metadata = metadata;
      this.setServiceName(this._metadata.name);
      this._metadata.input.forEach(input => {
        let label = new qx.ui.basic.Label(input.name);
        label.portId = qxapp.utils.Utils.uuidv4();
        label.type = input.type;
        label.setFocusable(true);
        qx.event.Registration.addListener(label, "focusin", this._onLabelFocusIn, this);
        qx.event.Registration.addListener(label, "focusout", this._onLabelFocusOut, this);
        this._inputPorts.add(label);
      });
      this._metadata.output.forEach(output => {
        let label = new qx.ui.basic.Label(output.name);
        label.portId = qxapp.utils.Utils.uuidv4();
        label.type = output.type;
        label.setFocusable(true);
        qx.event.Registration.addListener(label, "focusin", this._onLabelFocusIn, this);
        qx.event.Registration.addListener(label, "focusout", this._onLabelFocusOut, this);
        this._outputPorts.add(label);
      });
    }
  },

  events: {
    "PortSelected": "qx.event.type.Data"
  },

  properties: {
    nodeId: {
      check: "String",
      nullable: false
    }
  },

  members: {
    _metadata: null,
    _inputPorts: null,
    _outputPorts: null,
    _progressLabel: null,
    _inputLinkIDs: null,
    _outputLinkIDs: null,

    _onLabelFocusIn: function(e) {
      // console.log("event", e);
      console.log("Port Selected", e.getTarget());
      console.log("Node: ", this);
      // e.getTarget().setBackgroundColor("red");
      this.fireDataEvent("PortSelected", e.getTarget().portId);
    },

    _onLabelFocusOut: function(e) {
      // console.log("event", e);
      console.log("Port Unselected", e.getTarget());
      console.log("Node: ", this);
      // e.getTarget().resetBackgroundColor();
      this.fireDataEvent("PortSelected", e.getTarget().portId);
    },

    getMetaData: function() {
      return this._metadata;
    },

    setServiceName: function(name) {
      this.setCaption(name);
    },

    setInputs: function(names) {
      names.forEach(name => {
        let label = new qx.ui.basic.Label(name);
        this._inputPorts.add(label);
      });
    },

    setOutputs: function(names) {
      names.forEach(name => {
        let label = new qx.ui.basic.Label(name);
        this._outputPorts.add(label);
      });
    },

    addInputLinkID: function(linkID) {
      this._inputLinkIDs.push(linkID);
    },

    getInputLinkIDs: function() {
      return this._inputLinkIDs;
    },

    addOutputLinkID: function(linkID) {
      this._outputLinkIDs.push(linkID);
    },

    getOutputLinkIDs: function() {
      return this._outputLinkIDs;
    }
  }
});
