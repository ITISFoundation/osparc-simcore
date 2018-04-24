/* global qxapp */

qx.Class.define("qxapp.components.NodeBase", {
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

    this.setNodeId(qxapp.utils.utils.uuidv4());

    let nodeLayout = new qx.ui.layout.VBox(5, null, "separator-vertical");
    this.setLayout(nodeLayout);

    let inputsOutputsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(20));
    this.add(inputsOutputsLayout, {flex: 1});

    let inputsBox = new qx.ui.layout.VBox(5);
    inputsBox.setAlignX("left");
    this._inputsLabels = new qx.ui.container.Composite(inputsBox);
    inputsOutputsLayout.add(this._inputsLabels, {width: "50%"});

    let outputsBox = new qx.ui.layout.VBox(5);
    outputsBox.setAlignX("right");
    this._outputsLabels = new qx.ui.container.Composite(outputsBox);
    inputsOutputsLayout.add(this._outputsLabels, {width: "50%"});

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
        label.setFocusable(true);
        qx.event.Registration.addListener(label, "focusin", this._onLabelFocusIn, this);
        qx.event.Registration.addListener(label, "focusout", this._onLabelFocusOut, this);
        this._inputsLabels.add(label);
      });
      this._metadata.output.forEach(output => {
        let label = new qx.ui.basic.Label(output.name);
        label.setFocusable(true);
        qx.event.Registration.addListener(label, "focusin", this._onLabelFocusIn, this);
        qx.event.Registration.addListener(label, "focusout", this._onLabelFocusOut, this);
        this._outputsLabels.add(label);
      });
    }
  },

  events: {

  },

  properties: {
    nodeId: {
      check: "String",
      nullable: false
    }
  },

  members: {
    _metadata: null,
    _inputsLabels: null,
    _outputsLabels: null,
    _progressLabel: null,
    _inputLinkIDs: null,
    _outputLinkIDs: null,

    _onLabelFocusIn: function(e) {
      console.log("_onLabelFocusIn", e.getTarget());
      console.log(this);
      // e.getTarget().setBackgroundColor("red");
    },

    _onLabelFocusOut: function(e) {
      console.log("_onLabelFocusOut", e.getTarget());
      console.log(this);
      // e.getTarget().resetBackgroundColor();
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
        this._inputsLabels.add(label);
      });
    },

    setOutputs: function(names) {
      names.forEach(name => {
        let label = new qx.ui.basic.Label(name);
        this._outputsLabels.add(label);
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
