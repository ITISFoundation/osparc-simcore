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
 * Class that stores Node data.
 *
 *   For the given version-key, this class will take care of pulling the metadata, store it and
 * fill in all the information.
 *
 *                                    -> {EDGES}
 * STUDY -> METADATA + WORKBENCH ->|
 *                                    -> {LINKS}
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let node = new osparc.data.model.Node(key, version, uuid);
 *   node.populateNodeData(nodeData);
 *   node.startDynamicService();
 * </pre>
 */

qx.Class.define("osparc.data.model.Node", {
  extend: qx.core.Object,
  include: qx.locale.MTranslation,

  /**
    * @param study {osparc.data.model.Study} Study or Serialized Study Object
    * @param key {String} key of the service represented by the node
    * @param version {String} version of the service represented by the node
    * @param uuid {String} uuid of the service represented by the node (not needed for new Nodes)
  */
  construct: function(study, key, version, uuid) {
    this.base(arguments);

    this.__metaData = osparc.utils.Services.getMetaData(key, version);
    this.__innerNodes = {};
    this.setOutputs({});

    this.__inputNodes = [];
    this.__exposedNodes = [];

    if (study) {
      this.setStudy(study);
    }
    this.set({
      nodeId: uuid || osparc.utils.Utils.uuidv4(),
      key,
      version,
      status: new osparc.data.model.NodeStatus(this)
    });

    this.populateWithMetadata();
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      init: null,
      nullable: false,
      event: "changeStudy"
    },

    key: {
      check: "String",
      nullable: true,
      apply: "__applyNewMetaData"
    },

    version: {
      check: "String",
      nullable: true,
      event: "changeVersion",
      apply: "__applyNewMetaData"
    },

    nodeId: {
      check: "String",
      nullable: false
    },

    label: {
      check: "String",
      init: "Node",
      nullable: true,
      event: "changeLabel"
    },

    inputAccess: {
      check: "Object",
      nullable: true
    },

    parentNodeId: {
      check: "String",
      nullable: true
    },

    dynamicV2: {
      check: "Boolean",
      init: false,
      nullable: true
    },

    serviceUrl: {
      check: "String",
      nullable: true,
      event: "changeServiceUrl"
    },

    thumbnail: {
      check: "String",
      nullable: true,
      init: ""
    },

    portsConnected: {
      check: "Array",
      init: [],
      event: "changePortsConnected"
    },

    inputs: {
      check: "Object",
      // nullable: false,
      event: "changeInputs"
    },

    outputs: {
      check: "Object",
      nullable: false,
      event: "changeOutputs"
    },

    status: {
      check: "osparc.data.model.NodeStatus",
      nullable: false
    },

    errors: {
      check: "Array",
      init: [],
      nullable: true,
      event: "changeErrors",
      apply: "__applyErrors"
    },

    bootOptions: {
      check: "Object",
      init: null,
      nullable: true
    },

    // GUI elements //
    propsForm: {
      check: "osparc.component.form.renderer.PropForm",
      init: null,
      nullable: true,
      apply: "__applyPropsForm"
    },

    propsFormEditor: {
      check: "osparc.component.form.renderer.PropFormEditor",
      init: null,
      nullable: true
    },

    marker: {
      check: "qx.core.Object",
      init: null,
      nullable: true,
      event: "changeMarker"
    },

    inputConnected: {
      check: "Boolean",
      init: false,
      nullable: true,
      event: "changeInputConnected"
    },

    outputConnected: {
      check: "Boolean",
      init: false,
      nullable: true,
      event: "changeOutputConnected"
    },

    loadingPage: {
      check: "osparc.ui.message.Loading",
      init: null,
      nullable: true
    },

    iFrame: {
      check: "osparc.component.widget.PersistentIframe",
      init: null,
      nullable: true
    },

    logger: {
      check: "osparc.component.widget.logger.LoggerView",
      init: null,
      nullable: true
    }
    // GUI elements //
  },

  events: {
    "reloadModel": "qx.event.type.Event",
    "retrieveInputs": "qx.event.type.Data",
    "keyChanged": "qx.event.type.Event",
    "fileRequested": "qx.event.type.Data",
    "parameterRequested": "qx.event.type.Data",
    "filePickerRequested": "qx.event.type.Data",
    "probeRequested": "qx.event.type.Data",
    "showInLogger": "qx.event.type.Data",
    "outputListChanged": "qx.event.type.Event",
    "changeInputNodes": "qx.event.type.Event"
  },

  statics: {
    isFrontend: function(metaData) {
      return (metaData && metaData.key && metaData.key.includes("/frontend/"));
    },

    isFilePicker: function(metaData) {
      return (metaData && metaData.key && metaData.key.includes("file-picker"));
    },

    isParameter: function(metaData) {
      return (metaData && metaData.key && metaData.key.includes("/parameter/"));
    },

    isIterator: function(metaData) {
      return (metaData && metaData.key && metaData.key.includes("/data-iterator/"));
    },

    isProbe: function(metaData) {
      return (metaData && metaData.key && metaData.key.includes("/iterator-consumer/"));
    },

    isDynamic: function(metaData) {
      return (metaData && metaData.type && metaData.type === "dynamic");
    },

    isComputational: function(metaData) {
      return (metaData && metaData.type && metaData.type === "computational");
    },

    isUpdatable: function(metaData) {
      return osparc.utils.Services.isUpdatable(metaData);
    },

    isDeprecated: function(metaData) {
      return osparc.utils.Services.isDeprecated(metaData);
    },

    isRetired: function(metaData) {
      return osparc.utils.Services.isRetired(metaData);
    },

    hasBootModes: function(metaData) {
      if ("boot-options" in metaData && "boot_mode" in metaData["boot-options"] && "items" in metaData["boot-options"]["boot_mode"]) {
        return Object.keys(metaData["boot-options"]["boot_mode"]["items"]).length;
      }
      return false;
    },

    getBootModesSelectBox: function(nodeMetaData, workbench, nodeId) {
      if (!osparc.data.model.Node.hasBootModes(nodeMetaData)) {
        return null;
      }

      const bootModesMD = nodeMetaData["boot-options"]["boot_mode"];
      const bootModeSB = new qx.ui.form.SelectBox();
      const sbItems = [];
      Object.entries(bootModesMD["items"]).forEach(([bootModeId, bootModeMD]) => {
        const sbItem = new qx.ui.form.ListItem(bootModeMD["label"]);
        sbItem.bootModeId = bootModeId;
        bootModeSB.add(sbItem);
        sbItems.push(sbItem);
      });
      let defaultBMId = null;
      if (workbench && nodeId && "bootOptions" in workbench[nodeId] && "boot_mode" in workbench[nodeId]["bootOptions"]) {
        defaultBMId = workbench[nodeId]["bootOptions"]["boot_mode"];
      } else {
        defaultBMId = bootModesMD["default"];
      }
      sbItems.forEach(sbItem => {
        if (defaultBMId === sbItem.bootModeId) {
          bootModeSB.setSelection([sbItem]);
        }
      });
      return bootModeSB;
    },

    getMinVisibleInputs: function(metaData) {
      return ("min-visible-inputs" in metaData) ? metaData["min-visible-inputs"] : null;
    },

    getOutput: function(outputs, outputKey) {
      if (outputKey in outputs && "value" in outputs[outputKey]) {
        return outputs[outputKey]["value"];
      }
      return null;
    }
  },

  members: {
    __metaData: null,
    __innerNodes: null,
    __inputNodes: null,
    __exposedNodes: null,
    __settingsForm: null,
    __posX: null,
    __posY: null,
    __unresponsiveRetries: null,
    __stopRequestingStatus: null,

    getWorkbench: function() {
      return this.getStudy().getWorkbench();
    },

    getSlideshowInstructions: function() {
      const slideshow = this.getStudy().getUi().getSlideshow();
      return slideshow.getInstructions(this.getNodeId());
    },

    isInKey: function(str) {
      if (this.getMetaData() === null) {
        return false;
      }
      if (this.getKey() === null) {
        return false;
      }
      return this.getKey().includes(str);
    },

    isFilePicker: function() {
      return osparc.data.model.Node.isFilePicker(this.getMetaData());
    },

    isParameter: function() {
      return osparc.data.model.Node.isParameter(this.getMetaData());
    },

    isIterator: function() {
      return osparc.data.model.Node.isIterator(this.getMetaData());
    },

    isProbe: function() {
      return osparc.data.model.Node.isProbe(this.getMetaData());
    },

    isDynamic: function() {
      return osparc.data.model.Node.isDynamic(this.getMetaData());
    },

    isComputational: function() {
      return osparc.data.model.Node.isComputational(this.getMetaData());
    },

    isUpdatable: function() {
      return osparc.data.model.Node.isUpdatable(this.getMetaData());
    },

    isDeprecated: function() {
      return osparc.data.model.Node.isDeprecated(this.getMetaData());
    },

    isRetired: function() {
      return osparc.data.model.Node.isRetired(this.getMetaData());
    },

    hasBootModes: function() {
      return osparc.data.model.Node.hasBootModes(this.getMetaData());
    },

    getMinVisibleInputs: function() {
      return osparc.data.model.Node.getMinVisibleInputs(this.getMetaData());
    },

    __applyNewMetaData: function() {
      this.__metaData = osparc.utils.Services.getMetaData(this.getKey(), this.getVersion());
    },

    getMetaData: function() {
      return this.__metaData;
    },

    __getInputData: function() {
      if (this.isPropertyInitialized("propsForm") && this.getPropsForm()) {
        return this.getPropsForm().getValues();
      }
      return {};
    },

    __getInputUnits: function() {
      if (this.isPropertyInitialized("propsForm") && this.getPropsForm()) {
        return this.getPropsForm().getChangedXUnits();
      }
      return {};
    },

    getInput: function(inputId) {
      return this.getInputs()[inputId];
    },

    getOutput: function(outputId) {
      return this.getOutputs()[outputId];
    },

    getFirstOutput: function() {
      const outputs = this.getOutputs();
      if (Object.keys(outputs).length) {
        return outputs[Object.keys(outputs)[0]];
      }
      return null;
    },

    hasInputs: function() {
      return Object.keys(this.getInputs()).length;
    },

    hasOutputs: function() {
      return Object.keys(this.getOutputs()).length;
    },

    getInnerNodes: function(recursive = false) {
      let innerNodes = Object.assign({}, this.__innerNodes);
      if (recursive) {
        for (const innerNodeId in this.__innerNodes) {
          let myInnerNodes = this.__innerNodes[innerNodeId].getInnerNodes(true);
          innerNodes = Object.assign(innerNodes, myInnerNodes);
        }
      }
      return innerNodes;
    },

    addInnerNode: function(innerNodeId, innerNode) {
      this.__innerNodes[innerNodeId] = innerNode;
    },

    populateWithMetadata: function() {
      const metaData = this.__metaData;
      if (metaData) {
        if (metaData.name) {
          this.setLabel(metaData.name);
        }
        if (metaData.inputs) {
          this.setInputs(metaData.inputs);
          if (Object.keys(metaData.inputs).length) {
            this.__addSettings(metaData.inputs);
            this.__addSettingsAccessLevelEditor(metaData.inputs);
          }
          if (this.getPropsForm()) {
            this.getPropsForm().makeInputsDynamic();
          }
        }
        if (metaData.outputs) {
          this.setOutputs(metaData.outputs);
        }
      }
    },

    populateNodeData: function(nodeData) {
      if (nodeData) {
        if (nodeData.label) {
          this.setLabel(nodeData.label);
        }
        this.populateInputOutputData(nodeData);
        this.populateStates(nodeData);
        if (nodeData.thumbnail) {
          this.setThumbnail(nodeData.thumbnail);
        }
        if (nodeData.bootOptions) {
          this.setBootOptions(nodeData.bootOptions);
        }
      }

      this.__initLogger();
      if (this.isDynamic()) {
        this.__initIFrame();
      }

      if (this.isParameter()) {
        this.__initParameter();
      }
    },

    populateNodeUIData: function(nodeUIData) {
      if ("position" in nodeUIData) {
        this.setPosition(nodeUIData.position);
      }
      if ("marker" in nodeUIData) {
        this.__addMarker(nodeUIData.marker);
      }
    },

    populateInputOutputData: function(nodeData) {
      this.__setInputData(nodeData.inputs);
      this.__setInputUnits(nodeData.inputsUnits);
      this.__setInputDataAccess(nodeData.inputAccess);
      if (this.getPropsForm()) {
        this.getPropsForm().makeInputsDynamic();
      }
      this.setOutputData(nodeData.outputs);
      this.addInputNodes(nodeData.inputNodes);
      this.addOutputNodes(nodeData.outputNodes);
    },

    populateStates: function(nodeData) {
      if ("progress" in nodeData) {
        const progress = Number.parseInt(nodeData["progress"]);
        const oldProgress = this.getStatus().getProgress();
        if (this.isFilePicker() && oldProgress > 0 && oldProgress < 100) {
          // file is being uploaded
          this.getStatus().setProgress(oldProgress);
        } else {
          this.getStatus().setProgress(progress);
        }
      }
      if ("state" in nodeData) {
        this.getStatus().setState(nodeData.state);
      }
    },

    startInBackend: function() {
      // create the node in the backend here
      const key = this.getKey();
      const version = this.getVersion();
      const params = {
        url: {
          studyId: this.getStudy().getUuid()
        },
        data: {
          "service_id": this.getNodeId(),
          "service_key": key,
          "service_version": version
        }
      };
      osparc.data.Resources.fetch("studies", "addNode", params)
        .then(() => {
          // a POST call on /nodes also triggers :start
          this.startDynamicService();
        })
        .catch(err => {
          let errorMsg = this.tr("Error when starting ") + key + ":" + version;
          this.getStatus().setInteractive("failed");
          if ("status" in err && err.status === 406) {
            errorMsg = this.getKey() + ":" + this.getVersion() + this.tr(" is retired");
            this.getStatus().setInteractive("retired");
          }
          const errorMsgData = {
            nodeId: this.getNodeId(),
            msg: errorMsg,
            level: "ERROR"
          };
          this.fireDataEvent("showInLogger", errorMsgData);
          osparc.component.message.FlashMessenger.getInstance().logAs(errorMsg, "ERROR");
        });
    },

    __applyPropsForm: function() {
      const checkIsPipelineRunning = () => {
        const isPipelineRunning = this.getStudy().isPipelineRunning();
        this.getPropsForm().setEnabled(!isPipelineRunning);
      };
      this.getStudy().addListener("changeState", () => checkIsPipelineRunning(), this);
      checkIsPipelineRunning();
    },

    /**
     * Add settings widget with those inputs that can be represented in a form
     */
    __addSettings: function(inputs) {
      const form = this.__settingsForm = new osparc.component.form.Auto(inputs);
      const propsForm = new osparc.component.form.renderer.PropForm(form, this, this.getStudy());
      this.setPropsForm(propsForm);
      propsForm.addListener("linkFieldModified", e => {
        const linkFieldModified = e.getData();
        const portId = linkFieldModified.portId;

        const oldPortsConnected = this.getPortsConnected();
        const portConnected = oldPortsConnected.find(connection => Object.keys(connection)[0] === portId);
        if (linkFieldModified.added && !(portConnected)) {
          const newConnection = {};
          newConnection[portId] = linkFieldModified.fromNodeId;
          const portsConnected = [];
          oldPortsConnected.forEach(oldPortConnected => portsConnected.push(oldPortConnected));
          portsConnected.push(newConnection);
          this.setPortsConnected(portsConnected);
        }
        if (!linkFieldModified.added && portConnected) {
          const idx = oldPortsConnected.indexOf(portConnected);
          if (idx > -1) {
            oldPortsConnected.splice(idx, 1);
          }
          const portsConnected = [];
          oldPortsConnected.forEach(oldPortConnected => portsConnected.push(oldPortConnected));
          this.setPortsConnected(portsConnected);
        }

        this.callRetrieveInputs(portId);
      }, this);

      [
        "fileRequested",
        "parameterRequested"
      ].forEach(nodeRequestSignal => {
        propsForm.addListener(nodeRequestSignal, e => {
          const portId = e.getData();
          this.fireDataEvent(nodeRequestSignal, {
            portId,
            nodeId: this.getNodeId()
          });
        }, this);
      });

      propsForm.addListener("filePickerRequested", e => {
        const data = e.getData();
        this.fireDataEvent("filePickerRequested", {
          portId: data.portId,
          nodeId: this.getNodeId(),
          file: data.file
        });
      }, this);
    },

    __addSettingsAccessLevelEditor: function(inputs) {
      const propsForm = this.getPropsForm();
      const form = new osparc.component.form.Auto(inputs);
      form.setData(this.__settingsForm.getData());
      const propsFormEditor = new osparc.component.form.renderer.PropFormEditor(form, this);
      this.__settingsForm.addListener("changeData", e => {
        // apply data
        const data = this.__settingsForm.getData();
        form.setData(data);
      }, this);
      propsForm.addListener("linkFieldModified", e => {
        const linkFieldModified = e.getData();
        const {
          portId,
          added
        } = linkFieldModified;
        if (added) {
          const srcControlLink = propsForm.getControlLink(portId);
          const controlLink = new qx.ui.form.TextField().set({
            enabled: false
          });
          srcControlLink.bind("value", controlLink, "value");
          propsFormEditor.linkAdded(portId, controlLink);
        } else {
          propsFormEditor.linkRemoved(portId);
        }
      }, this);
      this.setPropsFormEditor(propsFormEditor);
    },

    removeNodePortConnections: function(inputNodeId) {
      let inputs = this.__getInputData();
      for (const portId in inputs) {
        if (inputs[portId] && Object.prototype.hasOwnProperty.call(inputs[portId], "nodeUuid")) {
          if (inputs[portId]["nodeUuid"] === inputNodeId) {
            this.getPropsForm().removePortLink(portId);
          }
        }
      }
    },

    toggleMarker: function() {
      if (this.getMarker()) {
        this.__removeMarker();
      } else {
        this.__addMarker();
      }
    },

    __addMarker: function(marker) {
      if (marker === undefined) {
        marker = {
          color: osparc.utils.Utils.getRandomColor()
        };
      }
      const markerModel = qx.data.marshal.Json.createModel(marker, true);
      this.setMarker(markerModel);
    },

    __removeMarker: function() {
      this.setMarker(null);
    },

    __setInputData: function(inputs) {
      if (this.__settingsForm && inputs) {
        const inputData = {};
        const inputLinks = {};
        const inputsCopy = osparc.utils.Utils.deepCloneObject(inputs);
        for (let key in inputsCopy) {
          if (osparc.utils.Ports.isDataALink(inputsCopy[key])) {
            inputLinks[key] = inputsCopy[key];
          } else {
            inputData[key] = inputsCopy[key];
          }
        }
        this.getPropsForm().addPortLinks(inputLinks);
        this.__settingsForm.setData(inputData);
      }
    },

    __setInputUnits: function(inputsUnits) {
      if (this.__settingsForm && inputsUnits) {
        this.getPropsForm().setInputsUnits(inputsUnits);
      }
    },

    __setInputDataAccess: function(inputAccess) {
      if (inputAccess) {
        this.setInputAccess(inputAccess);
        this.getPropsForm().setAccessLevel(inputAccess);
        this.getPropsFormEditor().setAccessLevel(inputAccess);
      }

      const study = this.getStudy();
      if (study && study.isReadOnly() && this.getPropsForm()) {
        this.getPropsForm().setEnabled(false);
      }
    },

    setOutputData: function(outputs) {
      if (outputs) {
        let hasOutputs = false;
        for (const outputKey in this.getOutputs()) {
          if (!Object.prototype.hasOwnProperty.call(this.getOutputs(), outputKey)) {
            this.getOutputs()[outputKey] = {};
          }
          if (Object.prototype.hasOwnProperty.call(outputs, outputKey)) {
            this.getOutputs()[outputKey]["value"] = outputs[outputKey];
            hasOutputs = true;
          } else {
            this.getOutputs()[outputKey]["value"] = "";
          }
        }
        this.getStatus().setHasOutputs(hasOutputs);

        if (hasOutputs && (this.isFilePicker() || this.isParameter() || this.isDynamic())) {
          this.getStatus().setModified(false);
        }

        this.fireDataEvent("changeOutputs", this.getOutputs());
      }
    },

    __getOutputData: function(outputKey) {
      const outputs = this.getOutputs();
      if (outputKey in outputs && "value" in outputs[outputKey]) {
        return outputs[outputKey]["value"];
      }
      return null;
    },

    __getOutputsData: function() {
      const outputsData = {};
      Object.keys(this.getOutputs()).forEach(outKey => {
        const outData = this.__getOutputData(outKey);
        if (outData !== null) {
          outputsData[outKey] = outData;
        }
      });
      return outputsData;
    },

    requestFileUploadAbort: function() {
      if (this.isFilePicker()) {
        this["fileUploadAbortRequested"] = true;
      }
    },

    __applyErrors: function(errors) {
      if (errors && errors.length) {
        errors.forEach(error => {
          const loc = error["loc"];
          if (loc.length < 2) {
            return;
          }
          if (loc[1] === this.getNodeId()) {
            const errorMsgData = {
              nodeId: this.getNodeId(),
              msg: error["msg"],
              level: "ERROR"
            };

            // errors to port
            if (loc.length > 2) {
              const portKey = loc[2];
              if (this.hasInputs() && portKey in this.getMetaData()["inputs"]) {
                errorMsgData["msg"] = this.getMetaData()["inputs"][portKey]["label"] + ": " + errorMsgData["msg"];
              } else {
                errorMsgData["msg"] = portKey + ": " + errorMsgData["msg"];
              }
              this.getPropsForm().setPortErrorMessage(portKey, errorMsgData["msg"]);
            }

            // errors to logger
            this.fireDataEvent("showInLogger", errorMsgData);
          }
        });
      } else if (this.hasInputs()) {
        // reset port errors
        Object.keys(this.getMetaData()["inputs"]).forEach(portKey => {
          this.getPropsForm().setPortErrorMessage(portKey, null);
        });
      }
    },

    // Iterate over output ports and connect them to first compatible input port
    createAutoPortConnection: async function(node1, node2) {
      const preferencesSettings = osparc.desktop.preferences.Preferences.getInstance();
      if (!preferencesSettings.getAutoConnectPorts()) {
        return;
      }

      // create automatic port connections
      let autoConnections = 0;
      const outPorts = node1.getOutputs();
      const inPorts = node2.getInputs();
      for (const outPort in outPorts) {
        for (const inPort in inPorts) {
          if (await node2.addPortLink(inPort, node1.getNodeId(), outPort)) {
            autoConnections++;
            break;
          }
        }
      }
      if (autoConnections) {
        const flashMessenger = osparc.component.message.FlashMessenger.getInstance();
        flashMessenger.logAs(autoConnections + this.tr(" ports auto connected"), "INFO");
      }
    },

    addPortLink: function(toPortId, fromNodeId, fromPortId) {
      return new Promise(resolve => {
        const fromNode = this.getWorkbench().getNode(fromNodeId);
        osparc.utils.Ports.arePortsCompatible(fromNode, fromPortId, this, toPortId)
          .then(compatible => {
            if (compatible) {
              resolve(this.getPropsForm().addPortLink(toPortId, fromNodeId, fromPortId));
            } else {
              resolve(false);
            }
          });
      });
    },

    getLinks: function() {
      const links = this.getPropsForm() ? this.getPropsForm().getLinks() : [];
      return links;
    },

    // ----- Input Nodes -----
    getInputNodes: function() {
      return this.__inputNodes;
    },

    addInputNode: function(inputNodeId) {
      if (!this.__inputNodes.includes(inputNodeId)) {
        this.__inputNodes.push(inputNodeId);
        this.fireEvent("changeInputNodes");
        return true;
      }
      return false;
    },

    addInputNodes: function(inputNodes) {
      if (inputNodes) {
        inputNodes.forEach(inputNode => {
          this.addInputNode(inputNode);
        });
      }
    },

    removeInputNode: function(inputNodeId) {
      const index = this.__inputNodes.indexOf(inputNodeId);
      if (index > -1) {
        // remove node connection
        this.__inputNodes.splice(index, 1);
        this.fireDataEvent("changeInputNodes");
        return true;
      }
      return false;
    },

    isInputNode: function(inputNodeId) {
      const index = this.__inputNodes.indexOf(inputNodeId);
      return (index > -1);
    },
    // !---- Input Nodes -----

    // ----- Output Nodes -----
    getOutputNodes: function() {
      return this.__exposedNodes;
    },

    addOutputNodes: function(outputNodes) {
      if (outputNodes) {
        outputNodes.forEach(outputNode => {
          this.addOutputNode(outputNode);
        });
      }
    },

    addOutputNode: function(outputNodeId) {
      if (!this.__exposedNodes.includes(outputNodeId)) {
        this.__exposedNodes.push(outputNodeId);
        this.fireEvent("outputListChanged");
        return true;
      }
      return false;
    },

    removeOutputNode: function(outputNodeId) {
      const index = this.__exposedNodes.indexOf(outputNodeId);
      if (index > -1) {
        // remove node connection
        this.__exposedNodes.splice(index, 1);
        this.fireEvent("outputListChanged");
      }
      return false;
    },

    isOutputNode: function(outputNodeId) {
      const index = this.__exposedNodes.indexOf(outputNodeId);
      return (index > -1);
    },
    // !---- Output Nodes -----

    canNodeStart: function() {
      return this.isDynamic() && ["idle", "failed"].includes(this.getStatus().getInteractive());
    },

    requestStartNode: function() {
      if (!this.canNodeStart()) {
        return false;
      }
      const params = {
        url: {
          studyId: this.getStudy().getUuid(),
          nodeId: this.getNodeId()
        }
      };
      osparc.data.Resources.fetch("studies", "startNode", params)
        .then(() => this.startDynamicService())
        .catch(err => {
          if ("status" in err && err.status === 409) {
            osparc.component.message.FlashMessenger.getInstance().logAs(err.message, "WARNING");
          } else {
            console.error(err);
          }
        });
      return true;
    },

    requestStopNode: function() {
      const preferencesSettings = osparc.desktop.preferences.Preferences.getInstance();
      if (preferencesSettings.getConfirmStopNode()) {
        const msg = this.tr("Do you really want Stop and Save the current state?");
        const win = new osparc.ui.window.Confirmation(msg).set({
          confirmText: this.tr("Stop")
        });
        win.center();
        win.open();
        win.addListener("close", () => {
          if (win.getConfirmed()) {
            const params = {
              url: {
                studyId: this.getStudy().getUuid(),
                nodeId: this.getNodeId()
              }
            };
            osparc.data.Resources.fetch("studies", "stopNode", params)
              .then(() => this.stopDynamicService())
              .catch(err => console.error(err));
          }
        }, this);
      }
    },

    renameNode: function(newLabel) {
      if (!osparc.data.Permissions.getInstance().canDo("study.node.rename", true)) {
        return false;
      }
      this.setLabel(newLabel);
      return true;
    },

    __initLogger: function() {
      this.setLogger(new osparc.component.widget.logger.LoggerView());
    },

    __getLoadingPageHeader: function() {
      let statusText = this.tr("Starting");
      const status = this.getStatus().getInteractive();
      if (status) {
        statusText = status.charAt(0).toUpperCase() + status.slice(1);
      }
      return statusText + " " + this.getLabel() + " <span style='font-size: 16px;font-weight: normal;'><sub>v" + this.getVersion() + "</sub></span>";
    },

    __addDisclaimer: function(loadingPage) {
      if (this.getKey() && this.getKey().includes("pub-nat-med")) {
        loadingPage.set({
          disclaimer: this.tr("This might take a couple of minutes")
        });
      }
      if (
        (this.getKey() && this.getKey().includes("sim4life-lite")) ||
        osparc.product.Utils.isProduct("tis")
      ) {
        // show disclaimer after 1'
        setTimeout(() => {
          if (loadingPage) {
            loadingPage.set({
              disclaimer: this.tr("Platform demand is currently exceptional and efforts are underway to increase system capacity.<br>There may be a delay of a few minutes in starting services.")
            });
          }
        }, 60*1000);
      }
      return null;
    },

    __initLoadingPage: function() {
      const showZoomMaximizeButton = !osparc.product.Utils.isProduct("s4llite");
      const loadingPage = new osparc.ui.message.Loading(showZoomMaximizeButton);
      loadingPage.set({
        header: this.__getLoadingPageHeader()
      });
      this.__addDisclaimer(loadingPage);

      const thumbnail = this.getMetaData()["thumbnail"];
      if (thumbnail) {
        loadingPage.setLogo(thumbnail);
      }
      this.addListener("changeLabel", () => loadingPage.setHeader(this.__getLoadingPageHeader()), this);

      const nodeStatus = this.getStatus();
      const sequenceWidget = nodeStatus.getProgressSequence().getWidgetForLoadingPage();
      nodeStatus.bind("interactive", sequenceWidget, "visibility", {
        converter: state => ["starting", "pulling", "pending", "connecting"].includes(state) ? "visible" : "excluded"
      });
      loadingPage.addExtraWidget(sequenceWidget);

      this.getStatus().addListener("changeInteractive", () => {
        loadingPage.setHeader(this.__getLoadingPageHeader());
        const status = this.getStatus().getInteractive();
        if (["idle", "failed"].includes(status)) {
          const startButton = new qx.ui.form.Button().set({
            label: this.tr("Start"),
            icon: "@FontAwesome5Solid/play/18",
            font: "text-18",
            allowGrowX: false,
            height: 32
          });
          startButton.addListener("execute", () => this.requestStartNode());
          loadingPage.addWidgetToMessages(startButton);
        } else {
          loadingPage.setMessages([]);
        }
      }, this);
      this.setLoadingPage(loadingPage);
    },

    __initIFrame: function() {
      this.__initLoadingPage();

      const iframe = new osparc.component.widget.PersistentIframe();
      if (osparc.product.Utils.isProduct("s4llite")) {
        iframe.setShowToolbar(false);
      }
      iframe.addListener("restart", () => this.__restartIFrame(), this);
      this.setIFrame(iframe);
    },

    __restartIFrame: function() {
      if (this.getServiceUrl() !== null) {
        const loadIframe = () => {
          const status = this.getStatus().getInteractive();
          // it might have been stopped
          if (status === "ready") {
            this.getIFrame().resetSource();
            this.getIFrame().setSource(this.getServiceUrl());
          }
        };

        // restart button pushed
        if (this.getIFrame().getSource().includes(this.getServiceUrl())) {
          loadIframe();
        }

        const loadingPage = this.getLoadingPage();
        const bounds = loadingPage.getBounds();
        const domEle = loadingPage.getContentElement().getDomElement();
        const boundsCR = domEle ? domEle.getBoundingClientRect() : null;
        if (bounds !== null && boundsCR && boundsCR.width > 0) {
          loadIframe();
        } else {
          // lazy loading
          loadingPage.addListenerOnce("appear", () => loadIframe(), this);
        }
      }
    },

    __initParameter: function() {
      if (this.isParameter() && this.__getOutputData("out_1") === null) {
        const type = osparc.component.node.ParameterEditor.getParameterOutputType(this);
        // set default values if none
        let val = null;
        switch (type) {
          case "boolean":
            val = true;
            break;
          case "number":
          case "integer":
            val = 1;
            break;
          case "array":
            val = "[1]";
            break;
        }
        if (val !== null) {
          osparc.component.node.ParameterEditor.setParameterOutputValue(this, val);
        }
      }
    },

    callRetrieveInputs: function(portKey) {
      const data = {
        node: this,
        portKey
      };
      this.fireDataEvent("retrieveInputs", data);
    },

    retrieveInputs: function(portKey = null) {
      if (this.isDynamic()) {
        if (!osparc.data.Permissions.getInstance().canDo("study.update")) {
          return;
        }
        const srvUrl = this.getServiceUrl();
        if (srvUrl) {
          const urlRetrieve = this.isDynamicV2() ? osparc.utils.Utils.computeServiceV2RetrieveUrl(this.getStudy().getUuid(), this.getNodeId()) : osparc.utils.Utils.computeServiceRetrieveUrl(srvUrl);
          const updReq = new qx.io.request.Xhr();
          const reqData = {
            "port_keys": portKey ? [portKey] : []
          };
          updReq.setRequestHeader("Content-Type", "application/json");
          updReq.set({
            url: urlRetrieve,
            method: "POST",
            requestData: qx.util.Serializer.toJson(reqData)
          });
          updReq.addListener("success", e => {
            let resp = e.getTarget().getResponse();
            if (typeof resp === "string") {
              resp = JSON.parse(resp);
            }
            const {
              data
            } = resp;
            if (portKey) {
              const sizeBytes = (data && ("size_bytes" in data)) ? data["size_bytes"] : 0;
              this.getPropsForm().retrievedPortData(portKey, true, sizeBytes);
            }
          }, this);
          [
            "fail",
            "error"
          ].forEach(failure => {
            updReq.addListener(failure, e => {
              const {
                error
              } = e.getTarget().getResponse();
              if (portKey) {
                this.getPropsForm().retrievedPortData(portKey, false);
              }
              console.error(failure, error);
              const errorMsgData = {
                nodeId: this.getNodeId(),
                msg: "Failed retrieving inputs",
                level: "ERROR"
              };
              this.fireDataEvent("showInLogger", errorMsgData);
            }, this);
          });
          updReq.send();

          if (portKey) {
            this.getPropsForm().retrievingPortData(portKey);
          }
        }
      }
    },

    startDynamicService: function() {
      if (this.isDynamic()) {
        this.getStatus().getProgressSequence().resetSequence();

        const metaData = this.getMetaData();
        const msg = "Starting " + metaData.key + ":" + metaData.version + "...";
        const msgData = {
          nodeId: this.getNodeId(),
          msg,
          level: "INFO"
        };
        this.fireDataEvent("showInLogger", msgData);

        this.__unresponsiveRetries = 5;
        this.__nodeState();
      }
    },

    stopDynamicService: function() {
      if (this.isDynamic()) {
        this.getStatus().getProgressSequence().resetSequence();

        const metaData = this.getMetaData();
        const msg = "Stopping " + metaData.key + ":" + metaData.version + "...";
        const msgData = {
          nodeId: this.getNodeId(),
          msg: msg,
          level: "INFO"
        };
        this.fireDataEvent("showInLogger", msgData);

        this.__unresponsiveRetries = 5;
        this.__nodeState(false);

        this.getIFrame().resetSource();
      }
    },

    __onNodeState: function(data, starting=true) {
      const serviceState = data["service_state"];
      const nodeId = data["service_uuid"];
      const status = this.getStatus();
      switch (serviceState) {
        case "idle": {
          status.setInteractive(serviceState);
          if (starting && this.__unresponsiveRetries>0) {
            // a bit of a hack. We will get rid of it when the backend pushes the states
            this.__unresponsiveRetries--;
            const interval = 2000;
            qx.event.Timer.once(() => this.__nodeState(starting), this, interval);
          }
          break;
        }
        case "pending": {
          if (data["service_message"]) {
            const serviceName = this.getLabel();
            const serviceMessage = data["service_message"];
            const msg = `The service "${serviceName}" is waiting for available ` +
              `resources. Please inform support and provide the following message ` +
              `in case this does not resolve in a few minutes: "${nodeId}" ` +
              `reported "${serviceMessage}"`;
            const msgData = {
              nodeId: this.getNodeId(),
              msg: msg,
              level: "INFO"
            };
            this.fireDataEvent("showInLogger", msgData);
          }
          status.setInteractive(serviceState);
          const interval = 10000;
          qx.event.Timer.once(() => this.__nodeState(starting), this, interval);
          break;
        }
        case "stopping":
        case "starting":
        case "pulling": {
          status.setInteractive(serviceState);
          const interval = 5000;
          qx.event.Timer.once(() => this.__nodeState(starting), this, interval);
          break;
        }
        case "running": {
          if (nodeId !== this.getNodeId()) {
            return;
          }
          if (!starting) {
            status.setInteractive("stopping");
            const interval = 5000;
            qx.event.Timer.once(() => this.__nodeState(starting), this, interval);
            break;
          }
          const {
            srvUrl,
            isDynamicV2
          } = osparc.utils.Utils.computeServiceUrl(data);
          this.setDynamicV2(isDynamicV2);
          if (srvUrl) {
            this.__waitForServiceReady(srvUrl);
          }
          break;
        }
        case "complete":
          break;
        case "failed": {
          status.setInteractive(serviceState);
          const msg = "Service failed: " + data["service_message"];
          const errorMsgData = {
            nodeId: this.getNodeId(),
            msg,
            lvel: "ERROR"
          };
          this.fireDataEvent("showInLogger", errorMsgData);
          return;
        }
        default:
          console.error(serviceState, "service state not supported");
          break;
      }
    },

    __nodeState: function(starting=true) {
      // Check if study is still there
      if (this.getStudy() === null || this.__stopRequestingStatus === true) {
        return;
      }
      // Check if node is still there
      if (this.getWorkbench().getNode(this.getNodeId()) === null) {
        return;
      }

      const params = {
        url: {
          studyId: this.getStudy().getUuid(),
          nodeId: this.getNodeId()
        }
      };
      osparc.data.Resources.fetch("studies", "getNode", params)
        .then(data => this.__onNodeState(data, starting))
        .catch(err => {
          let errorMsg = `Error retrieving ${this.getLabel()} status: ${err}`;
          if ("status" in err && err.status === 406) {
            errorMsg = this.getKey() + ":" + this.getVersion() + "is retired";
            this.getStatus().setInteractive("retired");
            osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was an error while starting the node."), "ERROR");
          }
          const errorMsgData = {
            nodeId: this.getNodeId(),
            msg: errorMsg,
            level: "ERROR"
          };
          this.fireDataEvent("showInLogger", errorMsgData);
          if ("status" in err && err.status === 406) {
            return;
          }
          if (this.__unresponsiveRetries > 0) {
            const retryMsg = `Retrying (${this.__unresponsiveRetries})`;
            const retryMsgData = {
              nodeId: this.getNodeId(),
              msg: retryMsg,
              level: "ERROR"
            };
            this.fireDataEvent("showInLogger", retryMsgData);
            this.__unresponsiveRetries--;
            const interval = Math.floor(Math.random() * 5000) + 3000;
            setTimeout(() => this.__nodeState(), interval);
          } else {
            this.getStatus().setInteractive("failed");
            osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was an error while starting the node."), "ERROR");
          }
        });
    },

    setNodeProgressSequence: function(progressType, progress) {
      const nodeStatus = this.getStatus();
      if (nodeStatus.getProgressSequence()) {
        nodeStatus.getProgressSequence().addProgressMessage(progressType, progress);
      }
    },

    __waitForServiceReady: function(srvUrl) {
      // ping for some time until it is really ready
      const pingRequest = new qx.io.request.Xhr(srvUrl);
      pingRequest.addListenerOnce("success", () => {
        this.__waitForServiceWebsite(srvUrl);
      }, this);
      pingRequest.addListenerOnce("fail", e => {
        const error = e.getTarget().getResponse();
        this.getStatus().setInteractive("connecting");
        console.log("service not ready yet, waiting... " + error);
        // Check if node is still there
        if (this.getWorkbench().getNode(this.getNodeId()) === null) {
          return;
        }
        const interval = 1000;
        qx.event.Timer.once(() => this.__waitForServiceReady(srvUrl), this, interval);
      });
      pingRequest.send();
    },

    __waitForServiceWebsite: function(srvUrl) {
      // request the frontend to make sure it is ready
      let retries = 5;
      const request = new XMLHttpRequest();
      const openAndSend = () => {
        if (retries === 0) {
          return;
        }
        retries--;
        request.open("GET", srvUrl);
        request.send();
      };
      const retry = () => {
        setTimeout(() => openAndSend(), 2000);
      };
      request.onerror = () => retry();
      request.ontimeout = () => retry();
      request.onload = () => {
        if (request.status < 200 || request.status >= 300) {
          retry();
        } else {
          this.__serviceReadyIn(srvUrl);
        }
      };
      openAndSend();
    },

    __serviceReadyIn: function(srvUrl) {
      this.setServiceUrl(srvUrl);
      this.getStatus().setInteractive("ready");
      const msg = "Service ready on " + srvUrl;
      const msgData = {
        nodeId: this.getNodeId(),
        msg,
        level: "INFO"
      };
      this.fireDataEvent("showInLogger", msgData);
      this.__restartIFrame();
      this.callRetrieveInputs();
    },

    attachHandlersToStartButton: function(startButton) {
      this.getStatus().bind("interactive", startButton, "visibility", {
        converter: state => (state === "ready") ? "excluded" : "visible"
      });
      this.getStatus().bind("interactive", startButton, "enabled", {
        converter: state => ["idle", "failed"].includes(state)
      });
      const executeListenerId = startButton.addListener("execute", this.requestStartNode, this);
      startButton.executeListenerId = executeListenerId;
    },

    attachVisibilityHandlerToStopButton: function(stopButton) {
      this.getStatus().bind("interactive", stopButton, "visibility", {
        converter: state => (state === "ready") ? "visible" : "excluded"
      });
    },

    attachEnabledHandlerToStopButton: function(stopButton) {
      this.getStatus().bind("interactive", stopButton, "enabled", {
        converter: state => state === "ready"
      });
    },

    attachExecuteHandlerToStopButton: function(stopButton) {
      const executeListenerId = stopButton.addListener("execute", this.requestStopNode, this);
      stopButton.executeListenerId = executeListenerId;
    },

    attachHandlersToStopButton: function(stopButton) {
      this.attachVisibilityHandlerToStopButton(stopButton);
      this.attachEnabledHandlerToStopButton(stopButton);
      this.attachExecuteHandlerToStopButton(stopButton);
    },

    removeNode: function() {
      return new Promise(resolve => {
        this.__deleteInBackend()
          .then(() => {
            resolve(true);
            this.removeIFrame();
          })
          .catch(err => {
            console.error(err);
            resolve(false);
          });
      });
    },

    __deleteInBackend: function() {
      // remove node in the backend
      const params = {
        url: {
          studyId: this.getStudy().getUuid(),
          nodeId: this.getNodeId()
        }
      };
      return osparc.data.Resources.fetch("studies", "deleteNode", params);
    },

    stopRequestingStatus: function() {
      this.__stopRequestingStatus = true;
    },

    removeIFrame: function() {
      let iFrame = this.getIFrame();
      if (iFrame) {
        iFrame.destroy();
        this.setIFrame(null);
      }
    },

    setPosition: function(pos) {
      const {
        x,
        y
      } = pos;
      // keep positions positive
      this.__posX = parseInt(x) < 0 ? 0 : parseInt(x);
      this.__posY = parseInt(y) < 0 ? 0 : parseInt(y);
    },

    getPosition: function() {
      return {
        x: this.__posX || 0,
        y: this.__posY || 0
      };
    },

    // "number", "boolean", "integer"
    convertToParameter: function(type) {
      if (!["int"].includes(type)) {
        return;
      }
      const newMetadata = osparc.utils.Services.getParameterMetadata("integer");
      if (newMetadata) {
        const value = this.__getInputData()["linspace_start"];
        const label = this.getLabel();
        this.setKey(newMetadata["key"]);
        this.populateWithMetadata();
        this.populateNodeData();
        this.setLabel(label);
        osparc.component.node.ParameterEditor.setParameterOutputValue(this, value);
        this.fireEvent("keyChanged");
      }
    },

    convertToIterator: function(type) {
      if (!["int"].includes(type)) {
        return;
      }
      const newKey = "simcore/services/frontend/data-iterator/int-range";
      if (newKey in osparc.utils.Services.servicesCached) {
        const value = this.__getOutputData("out_1");
        const label = this.getLabel();
        this.setKey(newKey);
        this.populateWithMetadata();
        this.populateNodeData();
        this.setLabel(label);
        this.__setInputData({
          "linspace_start": value,
          "linspace_stop": value,
          "linspace_step": 1
        });
        this.fireEvent("keyChanged");
      }
    },

    serialize: function(clean = true) {
      // node generic
      let nodeEntry = {
        key: this.getKey(),
        version: this.getVersion(),
        label: this.getLabel(),
        inputs: this.__getInputData(),
        inputsUnits: this.__getInputUnits(),
        inputAccess: this.getInputAccess(),
        inputNodes: this.getInputNodes(),
        parent: this.getParentNodeId(),
        thumbnail: this.getThumbnail(),
        bootOptions: this.getBootOptions()
      };
      if (!clean) {
        nodeEntry.progress = this.getStatus().getProgress();
        nodeEntry.outputs = this.__getOutputsData();
        nodeEntry.state = this.getStatus().serialize();
      }

      if (this.isFilePicker()) {
        nodeEntry.outputs = osparc.file.FilePicker.serializeOutput(this.getOutputs());
        nodeEntry.progress = this.getStatus().getProgress();
      } else if (this.isParameter()) {
        nodeEntry.outputs = this.__getOutputsData();
      }

      // remove null entries from the payload
      let filteredNodeEntry = {};
      for (const key in nodeEntry) {
        if (nodeEntry[key] !== null || key === "parent") {
          filteredNodeEntry[key] = nodeEntry[key];
        }
      }

      return filteredNodeEntry;
    }
  }
});
