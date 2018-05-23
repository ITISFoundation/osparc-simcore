qx.Class.define("qxapp.components.workbench.NodeBase", {
  extend: qx.ui.window.Window,

  construct: function() {
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

    let nodeLayout = new qx.ui.layout.VBox(5, null, "separator-vertical");
    this.setLayout(nodeLayout);

    let inputsOutputsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(20));
    this.add(inputsOutputsLayout, {
      flex: 1
    });

    let inputsBox = new qx.ui.layout.VBox(5);
    inputsBox.setAlignX("left");
    this.__inputPorts = new qx.ui.container.Composite(inputsBox);
    inputsOutputsLayout.add(this.__inputPorts, {
      width: "50%"
    });

    let outputsBox = new qx.ui.layout.VBox(5);
    outputsBox.setAlignX("right");
    this.__outputPorts = new qx.ui.container.Composite(outputsBox);
    inputsOutputsLayout.add(this.__outputPorts, {
      width: "50%"
    });

    let progressBox = new qx.ui.layout.HBox(5);
    progressBox.setAlignX("center");
    let progressLayout = new qx.ui.container.Composite(progressBox);
    this.__progressLabel = new qx.ui.basic.Label("0%");
    progressLayout.add(this.__progressLabel);
    this.add(progressLayout);

    this.setNodeId(qxapp.utils.Utils.uuidv4());
  },

  properties: {
    nodeId: {
      check: "String",
      nullable: false
    },

    nodeImageId: {
      check: "String",
      nullable: false
    },

    metadata: {
      apply : "__applyMetadata"
    },

    inputLinkIDs: {
      check: "Array",
      init: [],
      nullable: false
    },

    outputLinkIDs: {
      check: "Array",
      init: [],
      nullable: false
    },

    settingsWidget: {
      check: "qxapp.components.form.renderer.PropForm"
    }
  },

  members: {
    __inputPorts: null,
    __outputPorts: null,
    __progressLabel: null,
    __settingForm: null,

    __applyMetadata: function(metaData, old) {
      if (metaData != undefined) {
        this.setMetadata(metaData);
        this.setServiceName(metaData.name);
        this.setNodeImageId(metaData.id);
        let form = this.__settingsForm = new qxapp.components.form.Auto(metaData.settings);
        this.setSettingsWidget(new qxapp.components.form.renderer.PropForm(form));

        metaData.input.forEach(input => {
          let label = new qx.ui.basic.Label(input.name);
          label.portId = qxapp.utils.Utils.uuidv4();
          this.__inputPorts.add(label);
        });

        metaData.output.forEach(output => {
          let label = new qx.ui.basic.Label(output.name);
          label.portId = qxapp.utils.Utils.uuidv4();
          this.__outputPorts.add(label);
        });
      }
    },

    setServiceName: function(name) {
      this.setCaption(name);
    },

    setInputs: function(names) {
      names.forEach(name => {
        let label = new qx.ui.basic.Label(name);
        this.__inputPorts.add(label);
      });
    },

    setOutputs: function(names) {
      names.forEach(name => {
        let label = new qx.ui.basic.Label(name);
        this.__outputPorts.add(label);
      });
    },

    addInputLinkID: function(linkID) {
      this.getInputLinkIDs().push(linkID);
    },

    addOutputLinkID: function(linkID) {
      this.getOutputLinkIDs().push(linkID);
    }
  }
});
