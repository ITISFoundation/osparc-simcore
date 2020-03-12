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
 *   node.giveUniqueName();
 *   node.addDynamicButtons();
 *   node.startDynamicService();
 * </pre>
 */

qx.Class.define("osparc.data.model.Node", {
  extend: qx.core.Object,
  include: qx.locale.MTranslation,

  /**
    * @param key {String} key of the service represented by the node
    * @param version {String} version of the service represented by the node
    * @param uuid {String} uuid of the service represented by the node (not needed for new Nodes)
  */
  construct: function(key, version, uuid) {
    this.base(arguments);

    this.__metaData = {};
    this.__innerNodes = {};
    this.__inputs = {};
    this.__inputsDefault = {};
    this.__outputs = {};

    this.__inputNodes = [];
    this.__outputNodes = [];

    this.set({
      key,
      version,
      nodeId: uuid || osparc.utils.Utils.uuidv4()
    });

    let metaData = this.__metaData = osparc.utils.Services.getNodeMetaData(key, version);
    if (metaData) {
      if (metaData.name) {
        this.setLabel(metaData.name);
      }
      if (metaData.inputsDefault) {
        this.__addInputsDefault(metaData.inputsDefault);
      }
      if (metaData.inputs) {
        this.__addInputs(metaData.inputs);
      }
      if (metaData.outputs) {
        this.__addOutputs(metaData.outputs);
      }
    }
  },

  properties: {
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

    serviceUrl: {
      check: "String",
      nullable: true,
      event: "changeServiceUrl"
    },

    progress: {
      check: "Number",
      init: 0,
      event: "changeProgress"
    },

    thumbnail: {
      check: "String",
      nullable: true,
      init: ""
    },

    interactiveStatus: {
      check: "String",
      nullable: true,
      event: "changeInteractiveStatus"
    },

    propsWidget: {
      check: "osparc.component.form.renderer.PropForm",
      init: null,
      nullable: true
    },

    inputsMapper: {
      check: "osparc.component.widget.InputsMapper",
      init: null,
      nullable: true
    },

    iFrame: {
      check: "osparc.component.widget.PersistentIframe",
      init: null,
      nullable: true
    },

    restartIFrameButton: {
      check: "qx.ui.form.Button",
      init: null
    },

    retrieveIFrameButton: {
      check: "qx.ui.form.Button",
      init: null
    }
  },

  events: {
    "retrieveInputs": "qx.event.type.Data",
    "showInLogger": "qx.event.type.Data",
    "outputChanged": "qx.event.type.Data",
    "outputListChanged": "qx.event.type.Event"
  },

  statics: {
    isDynamic: function(metaData) {
      return (metaData && metaData.type && metaData.type === "dynamic");
    },

    isComputational: function(metaData) {
      return (metaData && metaData.type && metaData.type === "computational");
    },

    isFilePicker: function(metaData) {
      return (metaData && metaData.key && metaData.key.includes("file-picker"));
    },

    isRealService: function(metaData) {
      return (metaData && metaData.type && (metaData.key.includes("simcore/services/dynamic") || metaData.key.includes("simcore/services/comp")));
    }
  },

  members: {
    __metaData: null,
    __innerNodes: null,
    __inputNodes: null,
    __outputNodes: null,
    __settingsForm: null,
    __inputs: null,
    __inputsDefault: null,
    __inputsDefaultWidget: null,
    __outputs: null,
    __outputWidget: null,
    __posX: null,
    __posY: null,

    getWorkbench: function() {
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      return study.getWorkbench();
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

    isContainer: function() {
      return this.getKey().includes("nodes-group");
    },

    isDynamic: function() {
      return osparc.data.model.Node.isDynamic(this.getMetaData());
    },

    isComputational: function() {
      return osparc.data.model.Node.isComputational(this.getMetaData());
    },

    isFilePicker: function() {
      return osparc.data.model.Node.isFilePicker(this.getMetaData());
    },

    isRealService: function() {
      return osparc.data.model.Node.isRealService(this.getMetaData());
    },

    getMetaData: function() {
      return this.__metaData;
    },

    getInputValues: function() {
      if (this.isPropertyInitialized("propsWidget") && this.getPropsWidget()) {
        return this.getPropsWidget().getValues();
      }
      return {};
    },

    getInputsDefault: function() {
      return this.__inputsDefault;
    },

    getInput: function(outputId) {
      return this.__inputs[outputId];
    },

    getInputs: function() {
      return this.__inputs;
    },

    getOutput: function(outputId) {
      return this.__outputs[outputId];
    },

    getOutputs: function() {
      return this.__outputs;
    },

    getOutputValues: function() {
      let output = {};
      for (const outputId in this.__outputs) {
        if (this.__outputs[outputId].value) {
          output[outputId] = this.__outputs[outputId].value;
        }
      }
      return output;
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
      const workbench = osparc.store.Store.getInstance().getCurrentStudy()
        .getWorkbench();

      let outputNodes = [];
      for (let i=0; i<this.__outputNodes.length; i++) {
        const outputNode = workbench.getNode(this.__outputNodes[i]);
        if (outputNode.isContainer()) {
          let myOutputNodes = outputNode.getExposedInnerNodes();
          outputNodes = outputNodes.concat(myOutputNodes);
        } else {
          outputNodes.push(outputNode);
        }
      }
      const uniqueNodes = [...new Set(outputNodes)];
      return uniqueNodes;
    },

    populateNodeData: function(nodeData) {
      if (nodeData) {
        if (nodeData.label) {
          this.setLabel(nodeData.label);
        }

        this.setInputData(nodeData);
        this.setOutputData(nodeData);

        if (nodeData.inputNodes) {
          this.addInputNodes(nodeData.inputNodes);
        }

        if (nodeData.outputNodes) {
          this.addOutputNodes(nodeData.outputNodes);
        }

        if (nodeData.position) {
          this.setPosition(nodeData.position.x, nodeData.position.y);
        }

        if (nodeData.progress) {
          this.setProgress(nodeData.progress);
        }

        if (nodeData.thumbnail) {
          this.setThumbnail(nodeData.thumbnail);
        }
      }

      if (this.__inputsDefaultWidget) {
        this.__inputsDefaultWidget.populatePortsData();
      }
      if (this.__outputWidget) {
        this.__outputWidget.populatePortsData();
      }

      if (this.isDynamic()) {
        this.__showLoadingIFrame();
      }
    },

    giveUniqueName: function() {
      const label = this.getLabel();
      this.__giveUniqueName(label, 2);
    },

    __giveUniqueName: function(label, suffix) {
      const newLabel = label + "_" + suffix;
      const allModels = this.getWorkbench().getNodes(true);
      const nodes = Object.values(allModels);
      for (const node of nodes) {
        if (node.getNodeId() !== this.getNodeId() &&
            node.getLabel().localeCompare(this.getLabel()) === 0) {
          this.setLabel(newLabel);
          this.__giveUniqueName(label, suffix+1);
        }
      }
    },

    repopulateOutputPortData: function() {
      if (this.__outputWidget) {
        this.__outputWidget.populatePortsData();
      }
    },

    getInputsDefaultWidget: function() {
      return this.__inputsDefaultWidget;
    },

    __addInputsDefaultWidgets: function() {
      const isInputModel = false;
      this.__inputsDefaultWidget = new osparc.component.widget.NodePorts(this, isInputModel);
    },

    /**
     * Remove those inputs that can't be respresented in the settings form
     * (Those are needed for creating connections between nodes)
     *
     */
    __removeNonSettingInputs: function(inputs) {
      let filteredInputs = JSON.parse(JSON.stringify(inputs));
      for (const inputId in filteredInputs) {
        let input = filteredInputs[inputId];
        if (input.type.includes("data:application/s4l-api/")) {
          delete filteredInputs[inputId];
        }
      }
      return filteredInputs;
    },


    /**
     * Add mapper widget if any
     *
     */
    __addMapper: function(inputs) {
      let filteredInputs = JSON.parse(JSON.stringify(inputs));
      if (filteredInputs.mapper) {
        let inputsMapper = new osparc.component.widget.InputsMapper(this, filteredInputs["mapper"]);
        this.setInputsMapper(inputsMapper);
        delete filteredInputs["mapper"];
      }
      return filteredInputs;
    },

    /**
     * Add settings widget with those inputs that can be represented in a form
     *
     */
    __addSettings: function(inputs) {
      const form = this.__settingsForm = new osparc.component.form.Auto(inputs, this);
      form.addListener("linkAdded", e => {
        const changedField = e.getData();
        this.getPropsWidget().linkAdded(changedField);
      }, this);
      form.addListener("linkRemoved", e => {
        const changedField = e.getData();
        this.getPropsWidget().linkRemoved(changedField);
      }, this);

      const propsWidget = new osparc.component.form.renderer.PropForm(form, this);
      this.setPropsWidget(propsWidget);
      propsWidget.addListener("removeLink", e => {
        const changedField = e.getData();
        this.__settingsForm.removeLink(changedField);
      }, this);
      propsWidget.addListener("dataFieldModified", e => {
        const portId = e.getData();
        this.__retrieveInputs(portId);
      }, this);
    },

    removeNodePortConnections: function(inputNodeId) {
      let inputs = this.getInputValues();
      for (const portId in inputs) {
        if (inputs[portId] && Object.prototype.hasOwnProperty.call(inputs[portId], "nodeUuid")) {
          if (inputs[portId]["nodeUuid"] === inputNodeId) {
            this.__settingsForm.removeLink(portId);
          }
        }
      }
    },

    getOutputWidget: function() {
      return this.__outputWidget;
    },

    __addOutputWidget: function() {
      const isInputModel = true;
      this.__outputWidget = new osparc.component.widget.NodePorts(this, isInputModel);
    },

    __addInputsDefault: function(inputsDefault) {
      this.__inputsDefault = inputsDefault;

      this.__addInputsDefaultWidgets();
    },

    __addInputs: function(inputs) {
      this.__inputs = inputs;

      if (inputs === null) {
        return;
      }

      let filteredInputs = this.__removeNonSettingInputs(inputs);
      filteredInputs = this.__addMapper(filteredInputs);
      this.__addSettings(filteredInputs);
    },

    __addOutputs: function(outputs) {
      this.__outputs = outputs;

      this.__addOutputWidget();
    },

    setInputData: function(nodeData) {
      if (this.__settingsForm && nodeData) {
        this.__settingsForm.setData(nodeData.inputs);
        if ("inputAccess" in nodeData) {
          this.__settingsForm.setAccessLevel(nodeData.inputAccess);
          this.setInputAccess(nodeData.inputAccess);
        }
      }
    },

    setOutputData: function(nodeData) {
      if (nodeData.outputs) {
        for (const outputKey in nodeData.outputs) {
          if (!Object.prototype.hasOwnProperty.call(this.__outputs, outputKey)) {
            this.__outputs[outputKey] = {};
          }
          this.__outputs[outputKey]["value"] = nodeData.outputs[outputKey];
          this.fireDataEvent("outputChanged", outputKey);
        }
      }
    },

    // post edge creation routine
    edgeAdded: function(edge) {
      const inputNode = this.getWorkbench().getNode(edge.getInputNodeId());
      const outputNode = this.getWorkbench().getNode(edge.getOutputNodeId());
      this.__createAutoPortConnection(inputNode, outputNode);

      if (this.isInKey("multi-plot")) {
        const innerNodes = Object.values(this.getInnerNodes());
        for (let i=0; i<innerNodes.length; i++) {
          const innerNode = innerNodes[i];
          if (innerNode.addInputNode(inputNode.getNodeId())) {
            this.__createAutoPortConnection(inputNode, innerNode);
          }
        }
        this.__retrieveInputs();
      }
    },

    // Iterate over output ports and connect them to first compatible input port
    __createAutoPortConnection: function(node1, node2) {
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
          if (osparc.utils.Ports.arePortsCompatible(outPorts[outPort], inPorts[inPort])) {
            if (node2.addPortLink(inPort, node1.getNodeId(), outPort)) {
              autoConnections++;
              break;
            }
          }
        }
      }
      if (autoConnections) {
        const flashMessenger = osparc.component.message.FlashMessenger.getInstance();
        flashMessenger.logAs(autoConnections + this.tr(" ports auto connected"), "INFO");
      }
    },

    addPortLink: function(toPortId, fromNodeId, fromPortId) {
      return this.__settingsForm.addLink(toPortId, fromNodeId, fromPortId);
    },

    // ----- Input Nodes -----
    getInputNodes: function() {
      return this.__inputNodes;
    },

    addInputNodes: function(inputNodes) {
      if (inputNodes) {
        for (let i=0; i<inputNodes.length; i++) {
          this.addInputNode(inputNodes[i]);
        }
      }
    },

    addInputNode: function(inputNodeId) {
      if (!this.__inputNodes.includes(inputNodeId)) {
        this.__inputNodes.push(inputNodeId);
        return true;
      }
      return false;
    },

    removeInputNode: function(inputNodeId) {
      const index = this.__inputNodes.indexOf(inputNodeId);
      if (index > -1) {
        // remove node connection
        this.__inputNodes.splice(index, 1);
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
      return this.__outputNodes;
    },

    addOutputNodes: function(outputNodes) {
      if (outputNodes) {
        for (let i=0; i<outputNodes.length; i++) {
          this.addOutputNode(outputNodes[i]);
        }
      }
    },

    addOutputNode: function(outputNodeId) {
      if (!this.__outputNodes.includes(outputNodeId)) {
        this.__outputNodes.push(outputNodeId);
        this.fireEvent("outputListChanged");
        return true;
      }
      return false;
    },

    removeOutputNode: function(outputNodeId) {
      const index = this.__outputNodes.indexOf(outputNodeId);
      if (index > -1) {
        // remove node connection
        this.__outputNodes.splice(index, 1);
        this.fireEvent("outputListChanged");
      }
      return false;
    },

    isOutputNode: function(outputNodeId) {
      const index = this.__outputNodes.indexOf(outputNodeId);
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

    restartIFrame: function(loadThis) {
      if (this.getIFrame() === null) {
        this.setIFrame(new osparc.component.widget.PersistentIframe());
      }
      if (loadThis) {
        this.getIFrame().resetSource();
        this.getIFrame().setSource(loadThis);
      } else if (this.getServiceUrl() !== null) {
        this.getIFrame().resetSource();
        if (this.getKey().includes("3d-viewer")) {
          // HACK: add this argument to only load the defined colorMaps
          // https://github.com/Kitware/visualizer/commit/197acaf
          const srvUrl = this.getServiceUrl();
          let arg = "?serverColorMaps";
          if (srvUrl[srvUrl.length-1] !== "/") {
            arg = "/" + arg;
          }
          this.getIFrame().setSource(srvUrl + arg);
        } else {
          this.getIFrame().setSource(this.getServiceUrl());
        }

        if (this.getKey().includes("raw-graphs")) {
          // Listen to the postMessage from RawGraphs, posting a new graph
          window.addEventListener("message", e => {
            const {
              id,
              imgData
            } = e.data;
            if (imgData && id === "svgChange") {
              const img = document.createElement("img");
              img.src = imgData;
              this.setThumbnail(img.outerHTML);
            }
          }, false);
        }
      }
    },

    __showLoadingIFrame: function() {
      const loadingUri = osparc.utils.Utils.getLoaderUri();
      this.restartIFrame(loadingUri);
    },

    __retrieveInputs: function(portKey) {
      const data = {
        node: this,
        portKey
      };
      this.fireDataEvent("retrieveInputs", data);
    },

    retrieveInputs: function(portKey = null) {
      if (this.isDynamic() && this.isRealService()) {
        if (!osparc.data.Permissions.getInstance().canDo("study.update")) {
          return;
        }
        const srvUrl = this.getServiceUrl();
        if (srvUrl) {
          let urlUpdate = srvUrl + "/retrieve";
          urlUpdate = urlUpdate.replace("//retrieve", "/retrieve");
          const updReq = new qx.io.request.Xhr();
          const reqData = {
            "port_keys": portKey ? [portKey] : []
          };
          updReq.set({
            url: urlUpdate,
            method: "POST",
            requestData: qx.util.Serializer.toJson(reqData)
          });
          updReq.addListener("success", e => {
            const {
              data
            } = e.getTarget().getResponse();
            const sizeBytes = (data && ("size_bytes" in data)) ? data["size_bytes"] : 0;
            this.getPropsWidget().retrievedPortData(portKey, true, sizeBytes);
            console.log(data);
          }, this);
          updReq.addListener("fail", e => {
            const {
              error
            } = e.getTarget().getResponse();
            this.getPropsWidget().retrievedPortData(portKey, false);
            console.error("fail", error);
          }, this);
          updReq.addListener("error", e => {
            const {
              error
            } = e.getTarget().getResponse();
            this.getPropsWidget().retrievedPortData(portKey, false);
            console.error("error", error);
          }, this);
          updReq.send();

          this.getPropsWidget().retrievingPortData(portKey);
        }
      }
    },

    addDynamicButtons: function() {
      if (this.isDynamic() && this.isRealService()) {
        const retrieveBtn = new qx.ui.toolbar.Button(this.tr("Retrieve"), "@FontAwesome5Solid/spinner/14");
        osparc.utils.Utils.setIdToWidget(retrieveBtn, "nodeViewRetrieveBtn");
        retrieveBtn.addListener("execute", e => {
          this.__retrieveInputs();
        }, this);
        retrieveBtn.setEnabled(false);
        this.setRetrieveIFrameButton(retrieveBtn);

        const restartBtn = new qx.ui.toolbar.Button(this.tr("Restart"), "@FontAwesome5Solid/redo-alt/14");
        osparc.utils.Utils.setIdToWidget(restartBtn, "nodeViewRestartBtn");
        restartBtn.addListener("execute", e => {
          this.restartIFrame();
        }, this);
        restartBtn.setEnabled(false);
        this.setRestartIFrameButton(restartBtn);
      }
    },

    startDynamicService: function() {
      if (this.isDynamic() && this.isRealService()) {
        const metaData = this.getMetaData();

        const msg = "Starting " + metaData.key + ":" + metaData.version + "...";
        const msgData = {
          nodeId: this.getNodeId(),
          msg: msg
        };
        this.fireDataEvent("showInLogger", msgData);

        this.setProgress(0);
        this.setInteractiveStatus("starting");

        this.__nodeState();
      }
    },
    __onNodeState: function(data) {
      const serviceState = data["service_state"];
      switch (serviceState) {
        case "starting":
        case "pulling": {
          this.setInteractiveStatus("starting");
          const interval = 5000;
          qx.event.Timer.once(() => this.__nodeState(), this, interval);
          break;
        }
        case "pending": {
          this.setInteractiveStatus("pending");
          const interval = 10000;
          qx.event.Timer.once(() => this.__nodeState(), this, interval);
          break;
        }
        case "running": {
          const servicePath = data["service_basepath"];
          const entryPointD = data["entry_point"];
          const nodeId = data["service_uuid"];
          if (nodeId !== this.getNodeId()) {
            return;
          }
          if (servicePath) {
            const entryPoint = entryPointD ? ("/" + entryPointD) : "/";
            const srvUrl = servicePath + entryPoint;
            this.__serviceReadyIn(srvUrl);
          }
          break;
        }
        case "complete":
          break;
        case "failed": {
          this.setInteractiveStatus("failed");
          const msg = "Service failed: " + data["service_message"];
          const msgData = {
            nodeId: this.getNodeId(),
            msg: msg
          };
          this.fireDataEvent("showInLogger", msgData);
          return;
        }

        default:
          console.error(serviceState, "service state not supported");
          break;
      }
    },
    __nodeState: function() {
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const params = {
        url: {
          projectId: study.getUuid(),
          nodeId: this.getNodeId()
        }
      };
      osparc.data.Resources.fetch("studies", "getNode", params)
        .then(data => this.__onNodeState(data))
        .catch(err => {
          const errorMsg = "Error when retrieving " + this.getKey() + ":" + this.getVersion() + " status: " + err;
          const errorMsgData = {
            nodeId: this.getNodeId(),
            msg: errorMsg
          };
          this.fireDataEvent("showInLogger", errorMsgData);
          this.setInteractiveStatus("failed");
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
        const msgData = {
          nodeId: this.getNodeId(),
          msg: msg
        };
        this.fireDataEvent("showInLogger", msgData);
        return;
      }

      this.__nodeState();
    },

    __serviceReadyIn: function(srvUrl) {
      this.setServiceUrl(srvUrl);
      this.setInteractiveStatus("ready");
      const msg = "Service ready on " + srvUrl;
      const msgData = {
        nodeId: this.getNodeId(),
        msg: msg
      };
      this.fireDataEvent("showInLogger", msgData);

      this.getRetrieveIFrameButton().setEnabled(true);
      this.getRestartIFrameButton().setEnabled(true);
      this.setProgress(100);

      // FIXME: Apparently no all services are inmediately ready when they publish the port
      const waitFor = 4000;
      qx.event.Timer.once(ev => {
        this.restartIFrame();
      }, this, waitFor);

      this.__retrieveInputs();
    },

    removeNode: function() {
      this.removeIFrame();
      const innerNodes = Object.values(this.getInnerNodes());
      for (const innerNode of innerNodes) {
        innerNode.removeNode();
      }
      const parentNodeId = this.getParentNodeId();
      if (parentNodeId) {
        let parentNode = this.getWorkbench().getNode(parentNodeId);
        parentNode.removeInnerNode(this.getNodeId());
        parentNode.removeOutputNode(this.getNodeId());
      }
    },

    removeIFrame: function() {
      let iFrame = this.getIFrame();
      if (iFrame) {
        iFrame.destroy();
        this.setIFrame(null);
      }
    },

    setPosition: function(x, y) {
      this.__posX = parseInt(x);
      this.__posY = parseInt(y);
    },

    getPosition: function() {
      return {
        x: this.__posX,
        y: this.__posY
      };
    },

    serialize: function(saveContainers = true, savePosition = true) {
      if (!saveContainers && this.isContainer()) {
        return null;
      }

      // node generic
      let nodeEntry = {
        key: this.getKey(),
        version: this.getVersion(),
        label: this.getLabel(),
        inputs: this.getInputValues(),
        inputAccess: this.getInputAccess(),
        inputNodes: this.getInputNodes(),
        parent: this.getParentNodeId(),
        thumbnail: this.getThumbnail()
      };

      if (this.isContainer()) {
        nodeEntry.outputNodes = this.getOutputNodes();
      }

      if (this.isFilePicker()) {
        nodeEntry.outputs = this.getOutputValues();
        nodeEntry.progress = this.getProgress();
      }

      if (savePosition) {
        nodeEntry.position = {
          x: this.getPosition().x,
          y: this.getPosition().y
        };
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
