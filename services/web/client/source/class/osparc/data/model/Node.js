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

    this.__metaData = {};
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
      nullable: true
    },

    version: {
      check: "String",
      nullable: true
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

    hasChildren: function() {
      const innerNodes = this.getInnerNodes();
      if (innerNodes) {
        return Object.keys(innerNodes).length > 0;
      }
      return false;
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

    removeInnerNode: function(innerNodeId) {
      delete this.__innerNodes[innerNodeId];
    },

    isInnerNode: function(inputNodeId) {
      return (inputNodeId in this.__innerNodes);
    },

    getExposedInnerNodes: function() {
      const workbench = this.getWorkbench();

      let outputNodes = [];
      for (let i = 0; i < this.__exposedNodes.length; i++) {
        const outputNode = workbench.getNode(this.__exposedNodes[i]);
        outputNodes.push(outputNode);
      }
      const uniqueNodes = [...new Set(outputNodes)];
      return uniqueNodes;
    },

    getExposedNodeIDs: function() {
      const exposedInnerNodes = this.getExposedInnerNodes();
      const exposedNodeIDs = exposedInnerNodes.map(exposedInnerNode => exposedInnerNode.getNodeId());
      return exposedNodeIDs;
    },

    populateWithMetadata: function() {
      const metaData = this.__metaData = osparc.utils.Services.getMetaData(this.getKey(), this.getVersion());
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
      this.setOutputData(nodeData.outputs);
      this.addInputNodes(nodeData.inputNodes);
      this.addOutputNodes(nodeData.outputNodes);
    },

    populateStates: function(nodeData) {
      if ("progress" in nodeData) {
        const progress = Number.parseInt(nodeData["progress"]);
        this.getStatus().setProgress(progress);
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
        .then(data => {
          this.startDynamicService();
        })
        .catch(err => {
          const errorMsg = "Error when starting " + key + ":" + version + ": " + err.getTarget().getResponse()["error"];
          const errorMsgData = {
            nodeId: this.getNodeId(),
            msg: errorMsg,
            level: "ERROR"
          };
          this.fireDataEvent("showInLogger", errorMsgData);
          this.getStatus().setInteractive("failed");
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was an error while starting the node."), "ERROR");
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
      osparc.data.Resources.fetch("studies", "deleteNode", params)
        .catch(err => console.error(err));
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

    // post edge creation routine
    edgeAdded: function(edge) {
      const inputNode = this.getWorkbench().getNode(edge.getInputNodeId());
      const outputNode = this.getWorkbench().getNode(edge.getOutputNodeId());
      this.__createAutoPortConnection(inputNode, outputNode);
    },

    // Iterate over output ports and connect them to first compatible input port
    __createAutoPortConnection: async function(node1, node2) {
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
      const status = this.getStatus().getInteractive();
      const label = this.getLabel();
      if (status) {
        const sta = status.charAt(0).toUpperCase() + status.slice(1);
        const header = sta + " " + label;
        return header;
      }
      return this.tr("Starting ") + label;
    },

    __getExtraMessages: function() {
      if (this.getKey() && this.getKey().includes("pub-nat-med")) {
        return [
          this.tr("This might take a couple of minutes")
        ];
      }
      return [];
    },

    __initLoadingIPage: function() {
      const loadingPage = new osparc.ui.message.Loading(this.__getLoadingPageHeader(), this.__getExtraMessages(), true);
      this.addListener("changeLabel", () => loadingPage.setHeader(this.__getLoadingPageHeader()), this);
      this.getStatus().addListener("changeInteractive", () => loadingPage.setHeader(this.__getLoadingPageHeader()), this);
      this.setLoadingPage(loadingPage);
    },

    __initIFrame: function() {
      this.__initLoadingIPage();

      const iframe = new osparc.component.widget.PersistentIframe();
      osparc.utils.Utils.setIdToWidget(iframe, "PersistentIframe");
      iframe.addListener("restart", () => this.__restartIFrame(), this);
      this.setIFrame(iframe);
    },

    __restartIFrame: function() {
      if (this.getServiceUrl() !== null) {
        const loadIframe = () => {
          this.getIFrame().resetSource();
          this.getIFrame().setSource(this.getServiceUrl());
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
        const metaData = this.getMetaData();

        const msg = "Starting " + metaData.key + ":" + metaData.version + "...";
        const msgData = {
          nodeId: this.getNodeId(),
          msg: msg
        };
        this.fireDataEvent("showInLogger", msgData);

        const status = this.getStatus();
        status.setInteractive("starting");

        this.__unresponsiveRetries = 5;
        this.__nodeState();
      }
    },
    __onNodeState: function(data) {
      const serviceState = data["service_state"];
      const nodeId = data["service_uuid"];
      const status = this.getStatus();
      switch (serviceState) {
        case "idle": {
          status.setInteractive("idle");
          const interval = 2000;
          qx.event.Timer.once(() => this.__nodeState(), this, interval);
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
              msg: msg
            };
            this.fireDataEvent("showInLogger", msgData);
          }
          status.setInteractive("pending");
          const interval = 10000;
          qx.event.Timer.once(() => this.__nodeState(), this, interval);
          break;
        }
        case "starting":
        case "pulling": {
          status.setInteractive(serviceState);
          const interval = 5000;
          qx.event.Timer.once(() => this.__nodeState(), this, interval);
          break;
        }
        case "running": {
          if (nodeId !== this.getNodeId()) {
            return;
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
          status.setInteractive("failed");
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
    __nodeState: function() {
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
        .then(data => this.__onNodeState(data))
        .catch(err => {
          if ("status" in err && err.status === 503 && this.__unresponsiveRetries > 0) {
            this.__unresponsiveRetries--;
            const interval = Math.floor(Math.random() * 5000) + 3000;
            console.log(this.getNodeId(), "node unresponive, trying again in", interval, this.__unresponsiveRetries);
            setTimeout(() => this.__nodeState(), interval);
            return;
          }
          const errorMsg = "Error when retrieving " + this.getKey() + ":" + this.getVersion() + " status: " + err;
          const errorMsgData = {
            nodeId: this.getNodeId(),
            msg: errorMsg,
            level: "ERROR"
          };
          this.fireDataEvent("showInLogger", errorMsgData);
          this.getStatus().setInteractive("failed");
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was an error while starting the node."), "ERROR");
        });
    },
    __onInteractiveNodeStarted: function(e) {
      let req = e.getTarget();
      const {
        error
      } = req.getResponse();

      if (error) {
        const msg = "Error received: " + error;
        const errorMsgData = {
          nodeId: this.getNodeId(),
          msg,
          level: "ERROR"
        };
        this.fireDataEvent("showInLogger", errorMsgData);
        return;
      }

      this.__nodeState();
    },
    __waitForServiceReady: function(srvUrl) {
      // ping for some time until it is really ready
      const pingRequest = new qx.io.request.Xhr(srvUrl);
      pingRequest.addListenerOnce("success", () => {
        this.__serviceReadyIn(srvUrl);
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

    __serviceReadyIn: function(srvUrl) {
      this.setServiceUrl(srvUrl);
      this.getStatus().setInteractive("ready");
      const msg = "Service ready on " + srvUrl;
      const msgData = {
        nodeId: this.getNodeId(),
        msg: msg
      };
      this.fireDataEvent("showInLogger", msgData);

      // FIXME: Apparently no all services are inmediately ready when they publish the port
      // ping the service until it is accessible through the platform
      const waitFor = 500;
      qx.event.Timer.once(ev => {
        this.__restartIFrame();
      }, this, waitFor);

      this.callRetrieveInputs();
    },

    __removeInnerNodes: function() {
      const innerNodes = Object.values(this.getInnerNodes());
      for (let i = 0; i < innerNodes.length; i++) {
        innerNodes[i].removeNode();
      }
    },

    __detachFromParent: function() {
      const parentNodeId = this.getParentNodeId();
      if (parentNodeId) {
        const parentNode = this.getWorkbench().getNode(parentNodeId);
        parentNode.removeInnerNode(this.getNodeId());
        parentNode.removeOutputNode(this.getNodeId());
      }
    },

    removeNode: function() {
      this.__deleteInBackend();
      this.removeIFrame();
      this.__removeInnerNodes();
      this.__detachFromParent();
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
