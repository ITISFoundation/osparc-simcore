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
 * </pre>
 */

qx.Class.define("osparc.data.model.Node", {
  extend: qx.core.Object,
  include: qx.locale.MTranslation,

  /**
    * @param study {osparc.data.model.Study} Study or Serialized Study Object
    * @param metadata {Object} service's metadata
    * @param nodeId {String} uuid of the service represented by the node (not needed for new Nodes)
  */
  construct: function(study, metadata, nodeId) {
    this.base(arguments);

    this.__metaData = metadata;
    this.setOutputs({});
    this.__inputNodes = [];
    this.__inputsRequired = [];

    if (study) {
      this.setStudy(study);
    }
    this.set({
      nodeId: nodeId || osparc.utils.Utils.uuidV4(),
      key: metadata["key"],
      version: metadata["version"],
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
      event: "changeOutputs",
      apply: "__applyOutputs",
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
      check: "osparc.form.renderer.PropForm",
      init: null,
      nullable: true,
      apply: "__applyPropsForm"
    },

    outputsForm: {
      check: "osparc.widget.NodeOutputs",
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

    logger: {
      check: "osparc.widget.logger.LoggerView",
      init: null,
      nullable: true
    }
    // GUI elements //
  },

  events: {
    "updateStudyDocument": "qx.event.type.Event",
    "reloadModel": "qx.event.type.Event",
    "retrieveInputs": "qx.event.type.Data",
    "keyChanged": "qx.event.type.Event",
    "fileRequested": "qx.event.type.Data",
    "parameterRequested": "qx.event.type.Data",
    "filePickerRequested": "qx.event.type.Data",
    "probeRequested": "qx.event.type.Data",
    "fileUploaded": "qx.event.type.Event",
    "showInLogger": "qx.event.type.Data",
    "outputListChanged": "qx.event.type.Event",
    "changeInputNodes": "qx.event.type.Event",
    "changeInputsRequired": "qx.event.type.Event"
  },

  statics: {
    isFrontend: function(metadata) {
      return (metadata && metadata.key && metadata.key.includes("/frontend/"));
    },

    isFilePicker: function(metadata) {
      return (metadata && metadata.key && metadata.key.includes("file-picker"));
    },

    isParameter: function(metadata) {
      return (metadata && metadata.key && metadata.key.includes("/parameter/"));
    },

    isIterator: function(metadata) {
      return (metadata && metadata.key && metadata.key.includes("/data-iterator/"));
    },

    isProbe: function(metadata) {
      return (metadata && metadata.key && metadata.key.includes("/iterator-consumer/"));
    },

    isDynamic: function(metadata) {
      return (metadata && metadata.type && metadata.type === "dynamic");
    },

    isComputational: function(metadata) {
      return (metadata && metadata.type && metadata.type === "computational");
    },

    isUpdatable: function(metadata) {
      return osparc.service.Utils.isUpdatable(metadata);
    },

    isDeprecated: function(metadata) {
      return osparc.service.Utils.isDeprecated(metadata);
    },

    isRetired: function(metadata) {
      return osparc.service.Utils.isRetired(metadata);
    },

    hasBootModes: function(metadata) {
      if (metadata["bootOptions"] && "boot_mode" in metadata["bootOptions"] && "items" in metadata["bootOptions"]["boot_mode"]) {
        return Object.keys(metadata["bootOptions"]["boot_mode"]["items"]).length;
      }
      return false;
    },

    populateBootModes: function(bootModeSB, nodeMetadata, workbench, nodeId) {
      if (!osparc.data.model.Node.hasBootModes(nodeMetadata)) {
        return;
      }

      const bootModesMD = nodeMetadata["bootOptions"]["boot_mode"];
      const sbItems = [];
      bootModeSB.removeAll();
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
    },

    getBootModesSelectBox: function(nodeMetadata, workbench, nodeId) {
      if (!osparc.data.model.Node.hasBootModes(nodeMetadata)) {
        return null;
      }

      const bootModeSB = new qx.ui.form.SelectBox();
      this.populateBootModes(bootModeSB, nodeMetadata, workbench, nodeId);
      return bootModeSB;
    },

    getMinVisibleInputs: function(metadata) {
      return ("minVisibleInputs" in metadata) ? metadata["minVisibleInputs"] : null;
    },

    getOutput: function(outputs, outputKey) {
      if (outputKey in outputs && "value" in outputs[outputKey]) {
        return outputs[outputKey]["value"];
      }
      return null;
    },

    getLinkedNodeIds: function(nodeData) {
      const linkedNodeIds = new Set([]);
      if ("inputs" in nodeData) {
        Object.values(nodeData["inputs"]).forEach(link => {
          if (link && typeof link === "object" && "nodeUuid" in link) {
            linkedNodeIds.add(link["nodeUuid"]);
          }
        });
      }
      return Array.from(linkedNodeIds);
    },
  },

  members: {
    __metaData: null,
    __inputNodes: null,
    __inputsRequired: null,
    __settingsForm: null,
    __posX: null,
    __posY: null,
    __iframeHandler: null,

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

    __applyNewMetaData: function(newV, oldV) {
      if (oldV !== null) {
        const metadata = osparc.store.Services.getMetadata(this.getKey(), this.getVersion());
        if (metadata) {
          this.__metaData = metadata;
        }
      }
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

    populateWithMetadata: function() {
      const metadata = this.__metaData;
      if (metadata) {
        if (metadata.name) {
          this.setLabel(metadata.name);
        }
        if (metadata.inputs) {
          this.setInputs(metadata.inputs);
          if (Object.keys(metadata.inputs).length) {
            this.__addSettings(metadata.inputs);
          }
          if (this.getPropsForm()) {
            this.getPropsForm().makeInputsDynamic();
          }
        }
        if (metadata.outputs) {
          this.setOutputs(metadata.outputs);
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

      this.initIframeHandler();

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
      // backwards compatible
      this.setInputsRequired(nodeData.inputsRequired || []);
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

    initIframeHandler: function() {
      if (this.isDynamic()) {
        this.__iframeHandler = new osparc.data.model.IframeHandler(this.getStudy(), this);
      }
    },

    getIframeHandler: function() {
      return this.__iframeHandler;
    },

    getIFrame: function() {
      return this.getIframeHandler() ? this.getIframeHandler().getIFrame() : null;
    },

    setIFrame: function(iframe) {
      return this.getIframeHandler() ? this.getIframeHandler().setIFrame(iframe) : null;
    },

    getLoadingPage: function() {
      return this.getIframeHandler() ? this.getIframeHandler().getLoadingPage() : null;
    },

    __applyPropsForm: function() {
      const checkIsPipelineRunning = () => {
        const isPipelineRunning = this.getStudy().isPipelineRunning();
        this.getPropsForm().setEnabled(!isPipelineRunning);
      };
      this.getStudy().addListener("changeState", () => checkIsPipelineRunning(), this);

      // potentially disabling the inputs form might have side effects if the deserialization is not over
      if (this.getWorkbench().isDeserialized()) {
        checkIsPipelineRunning();
      } else {
        this.getWorkbench().addListener("changeDeserialized", e => {
          if (e.getData()) {
            checkIsPipelineRunning();
          }
        }, this);
      }
    },

    /**
     * Add settings widget with those inputs that can be represented in a form
     */
    __addSettings: function(inputs) {
      const form = this.__settingsForm = new osparc.form.Auto(inputs);
      const propsForm = new osparc.form.renderer.PropForm(form, this, this.getStudy());
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

    __applyOutputs: function() {
      if (!this.isPropertyInitialized("outputsForm") || !this.getOutputsForm()) {
        const nodeOutputs = new osparc.widget.NodeOutputs(this);
        this.setOutputsForm(nodeOutputs);
      }
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
        this.getPropsForm().setInputLinks(inputLinks);
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
      }

      const study = this.getStudy();
      if (study && study.isReadOnly() && this.getPropsForm()) {
        this.getPropsForm().setEnabled(false);
      }
    },

    setOutputData: function(outputs) {
      if (outputs) {
        let hasOutputs = false;
        Object.keys(this.getOutputs()).forEach(outputKey => {
          if (outputKey in outputs) {
            this.setOutputs({
              ...this.getOutputs(),
              [outputKey]: {
                ...this.getOutputs()[outputKey],
                value: outputs[outputKey]
              }
            });
            hasOutputs = true;
          } else {
            this.setOutputs({
              ...this.getOutputs(),
              [outputKey]: {
                ...this.getOutputs()[outputKey],
                value: ""
              }
            });
          }
        })
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
      const preferencesSettings = osparc.Preferences.getInstance();
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
        const flashMessenger = osparc.FlashMessenger.getInstance();
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

    getLink: function(portId) {
      const link = this.getPropsForm() ? this.getPropsForm().getLink(portId) : null;
      return link;
    },

    getLinks: function() {
      const links = this.getPropsForm() ? this.getPropsForm().getLinks() : [];
      return links;
    },

    getPortIds: function() {
      const portIds = this.getPropsForm() ? this.getPropsForm().getPortIds() : [];
      return portIds;
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

    // ----- Inputs Required -----
    getInputsRequired: function() {
      return this.__inputsRequired;
    },

    setInputsRequired: function(inputsRequired) {
      this.__inputsRequired = inputsRequired;
      this.fireEvent("changeInputsRequired");
    },

    toggleInputRequired: function(portId) {
      const inputsRequired = this.getInputsRequired();
      const index = inputsRequired.indexOf(portId);
      if (index > -1) {
        inputsRequired.splice(index, 1);
      } else {
        inputsRequired.push(portId);
      }
      this.setInputsRequired(inputsRequired);
    },
    // !---- Inputs Required -----

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
        .then(() => this.checkState())
        .catch(err => {
          if ("status" in err && (err.status === 409 || err.status === 402)) {
            osparc.FlashMessenger.getInstance().logAs(err.message, "WARNING");
          } else {
            console.error(err);
          }
        });
      return true;
    },

    requestStopNode: function(withConfirmationDialog=false) {
      const self = this;
      const stopService = () => {
        const params = {
          url: {
            studyId: self.getStudy().getUuid(),
            nodeId: self.getNodeId()
          }
        };
        osparc.data.Resources.fetch("studies", "stopNode", params)
          .then(() => self.stopDynamicService())
          .catch(err => console.error(err));
      };

      if (withConfirmationDialog) {
        const preferencesSettings = osparc.Preferences.getInstance();
        if (preferencesSettings.getConfirmStopNode()) {
          const msg = this.tr("Do you really want Stop and Save the current state?");
          const win = new osparc.ui.window.Confirmation(msg).set({
            caption: this.tr("Stop"),
            confirmText: this.tr("Stop")
          });
          win.center();
          win.open();
          win.addListener("close", () => {
            if (win.getConfirmed()) {
              stopService();
            }
          }, this);
        }
      } else {
        stopService();
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
      this.setLogger(new osparc.widget.logger.LoggerView());
    },

    __initParameter: function() {
      if (this.isParameter() && this.__getOutputData("out_1") === null) {
        const type = osparc.node.ParameterEditor.getParameterOutputType(this);
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
          osparc.node.ParameterEditor.setParameterOutputValue(this, val);
        }
      }
    },

    callRetrieveInputs: function(portKey) {
      const data = {
        node: this,
        portKey
      };
      if (this.isDynamic()) {
        this.fireDataEvent("retrieveInputs", data);
      }
    },

    retrieveInputs: function(portKey) {
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

    checkState: function() {
      if (this.isDynamic()) {
        const metadata = this.getMetaData();
        const msg = "Starting " + metadata.key + ":" + metadata.version + "...";
        const msgData = {
          nodeId: this.getNodeId(),
          msg,
          level: "INFO"
        };
        this.fireDataEvent("showInLogger", msgData);

        if (this.getIframeHandler()) {
          this.getIframeHandler().checkState();
        } else {
          console.error(this.getLabel() + " iframe handler not ready");
        }
      }
    },

    stopDynamicService: function() {
      if (this.isDynamic()) {
        const metadata = this.getMetaData();
        const msg = "Stopping " + metadata.key + ":" + metadata.version + "...";
        const msgData = {
          nodeId: this.getNodeId(),
          msg,
          level: "INFO"
        };
        this.fireDataEvent("showInLogger", msgData);

        this.getIframeHandler().stopIframe();
      }
    },

    setNodeProgressSequence: function(progressType, progressReport) {
      const nodeStatus = this.getStatus();
      if (nodeStatus.getProgressSequence()) {
        nodeStatus.getProgressSequence().addProgressMessage(progressType, progressReport);
      }
      // there might be some pending ``service_message`` still shown, remove it
      if (this.getIframeHandler()) {
        const loadingPage = this.getIframeHandler().getLoadingPage();
        loadingPage.clearMessages();
      }
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

    attachHandlersToStopButton: function(stopButton) {
      this.getStatus().bind("interactive", stopButton, "visibility", {
        converter: state => (state === "ready") ? "visible" : "excluded"
      });
      this.getStatus().bind("interactive", stopButton, "enabled", {
        converter: state => state === "ready"
      });
      const executeListenerId = stopButton.addListener("execute", this.requestStopNode, this);
      stopButton.executeListenerId = executeListenerId;
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
      const newMetadata = osparc.service.Utils.getParameterMetadata("integer");
      if (newMetadata) {
        const value = this.__getInputData()["linspace_start"];
        const label = this.getLabel();
        this.setKey(newMetadata["key"]);
        this.populateWithMetadata();
        this.populateNodeData();
        this.setLabel(label);
        osparc.node.ParameterEditor.setParameterOutputValue(this, value);
        this.fireEvent("keyChanged");
      }
    },

    convertToIterator: function(type) {
      if (!["int"].includes(type)) {
        return;
      }
      const metadata = osparc.service.Utils.getLatest("simcore/services/frontend/data-iterator/int-range")
      if (metadata) {
        const value = this.__getOutputData("out_1");
        const label = this.getLabel();
        this.setKey(metadata["key"]);
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
        inputsRequired: this.getInputsRequired(),
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
        if (nodeEntry[key] !== null) {
          filteredNodeEntry[key] = nodeEntry[key];
        }
      }

      return filteredNodeEntry;
    }
  }
});
