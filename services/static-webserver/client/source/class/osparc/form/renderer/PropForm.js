/* ************************************************************************
   Copyright: 2013 OETIKER+PARTNER AG
              2018 ITIS Foundation
   License:   MIT
   Authors:   Tobi Oetiker <tobi@oetiker.ch>
              Odei Maiz <odeimaiz>
   Utf8Check: äöü
************************************************************************ */

/**
 * An extension of the PropFormBase that is able to handle port-links.
 */

qx.Class.define("osparc.form.renderer.PropForm", {
  extend: osparc.form.renderer.PropFormBase,

  /**
   * @param form {osparc.form.Auto} form widget to embed
   * @param node {osparc.data.model.Node} Node owning the widget
   * @param study {osparc.data.model.Study} Study owning the node
   */
  construct: function(form, node, study) {
    if (study) {
      this.setStudy(study);
    }
    this.__ctrlLinkMap = {};
    this.__linkUnlinkStackMap = {};
    this.__fieldOptsBtnMap = {};

    this.base(arguments, form, node);

    this.__addLinkCtrls();

    this.setDroppable(true);
    this.__attachDragoverHighlighter();
  },

  events: {
    "highlightEdge": "qx.event.type.Data",
    "linkFieldModified": "qx.event.type.Data",
    "fileRequested": "qx.event.type.Data",
    "filePickerRequested": "qx.event.type.Data",
    "parameterRequested": "qx.event.type.Data",
    "changeChildVisibility": "qx.event.type.Event"
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      init: null,
      nullable: false
    }
  },

  statics: {
    getRetrievingAtom: function() {
      return new qx.ui.basic.Atom("", "osparc/loading.gif");
    },

    getDownloadingAtom: function() {
      return new qx.ui.basic.Atom("", "@FontAwesome5Solid/cloud-download-alt/12");
    },

    getUploadingAtom: function() {
      return new qx.ui.basic.Atom("", "@FontAwesome5Solid/cloud-upload-alt/12");
    },

    getFailedAtom: function() {
      return new qx.ui.basic.Atom("", "@FontAwesome5Solid/times/12");
    },

    getSucceededAtom: function() {
      return new qx.ui.basic.Atom("", "@FontAwesome5Solid/check/12");
    },

    getRetrievedEmpty: function() {
      return new qx.ui.basic.Atom("", "@FontAwesome5Solid/dot-circle/10");
    },

    GRID_POS: {
      ...osparc.form.renderer.PropFormBase.GRID_POS,
      RETRIEVE_STATUS: Object.keys(osparc.form.renderer.PropFormBase.GRID_POS).length
    },

    isFieldParametrizable: function(field) {
      const supportedTypes = [];
      const paramsMD = osparc.service.Utils.getParametersMetadata();
      paramsMD.forEach(paramMD => {
        supportedTypes.push(osparc.node.ParameterEditor.getParameterOutputTypeFromMD(paramMD));
      });
      return supportedTypes.includes(field.type);
    },

    RETRIEVE_STATUS: {
      failed: -1,
      empty: 0,
      retrieving: 1,
      downloading: 2,
      uploading: 3,
      succeed: 4
    },

    getIconForStatus: function(status) {
      let icon;
      switch (status) {
        case this.RETRIEVE_STATUS.failed:
          icon = this.getFailedAtom();
          break;
        case this.RETRIEVE_STATUS.empty:
          icon = this.getRetrievedEmpty();
          break;
        case this.RETRIEVE_STATUS.retrieving:
          icon = this.getRetrievingAtom();
          break;
        case this.RETRIEVE_STATUS.downloading:
          icon = this.getDownloadingAtom();
          break;
        case this.RETRIEVE_STATUS.uploading:
          icon = this.getUploadingAtom();
          break;
        case this.RETRIEVE_STATUS.succeed:
          icon = this.getSucceededAtom();
          break;
      }
      return icon;
    }
  },

  members: {
    __ctrlLinkMap: null,
    __linkUnlinkStackMap: null,
    __fieldOptsBtnMap: null,
    __addInputPortButton: null,

    /*
     * <-- Dynamic inputs -->
     */
    __getEmptyDataLastPorts: function() {
      let emptyDataPorts = [];
      const minVisibleInputs = this.getNode().getMinVisibleInputs();
      if (minVisibleInputs === null) {
        return emptyDataPorts;
      }
      const portIds = this.getPortIds();
      // it will always show 1 more, so: -1
      for (let i=minVisibleInputs-1; i<portIds.length; i++) {
        const portId = portIds[i];
        const ctrl = this._form.getControl(portId);
        if (ctrl && ctrl.type.includes("data:") && !("link" in ctrl)) {
          emptyDataPorts.push(portId);
        } else {
          emptyDataPorts = [];
        }
      }
      return emptyDataPorts;
    },

    __getVisibleEmptyDataLastPort: function() {
      let emptyDataPorts = null;
      this.getPortIds().forEach(portId => {
        const ctrl = this._form.getControl(portId);
        const label = this._getLabelFieldChild(portId).child;
        if (
          ctrl && ctrl.type.includes("data:") && !("link" in ctrl) &&
          label && label.isVisible()
        ) {
          emptyDataPorts = portId;
        }
      });
      return emptyDataPorts;
    },

    __addInputPortButtonClicked: function() {
      const emptyDataPorts = this.__getEmptyDataLastPorts();
      const lastEmptyDataPort = this.__getVisibleEmptyDataLastPort();
      if (emptyDataPorts.length>1 && lastEmptyDataPort) {
        const idx = emptyDataPorts.indexOf(lastEmptyDataPort);
        if (idx+1 < emptyDataPorts.length) {
          this.__showPort(emptyDataPorts[idx+1]);
        }
        this.__addInputPortButton.setVisibility(this.__checkAddInputPortButtonVisibility());
      }
    },

    __checkAddInputPortButtonVisibility: function() {
      const emptyDataPorts = this.__getEmptyDataLastPorts();
      const lastEmptyDataPort = this.__getVisibleEmptyDataLastPort();
      const idx = emptyDataPorts.indexOf(lastEmptyDataPort);
      if (idx < emptyDataPorts.length-1) {
        return "visible";
      }
      return "excluded";
    },

    __showPort: function(portId) {
      const entries = this.self().GRID_POS;
      Object.values(entries).forEach(entryPos => {
        const layoutElement = this._getLayoutChild(portId, entryPos);
        if (layoutElement && layoutElement.child) {
          const control = layoutElement.child;
          if (control) {
            control.show();
            const row = control.getLayoutProperties().row;
            this._getLayout().setRowHeight(row, osparc.form.renderer.PropFormBase.ROW_HEIGHT);
          }
        }
      });
    },

    __excludePort: function(portId) {
      const entries = this.self().GRID_POS;
      Object.values(entries).forEach(entryPos => {
        const layoutElement = this._getLayoutChild(portId, entryPos);
        if (layoutElement && layoutElement.child) {
          const control = layoutElement.child;
          if (control) {
            control.exclude();
            const row = control.getLayoutProperties().row;
            this._getLayout().setRowHeight(row, 0);
          }
        }
      });
    },

    makeInputsDynamic: function() {
      this.getPortIds().forEach(portId => this.__showPort(portId));

      const emptyDataPorts = this.__getEmptyDataLastPorts();
      for (let i=1; i<emptyDataPorts.length; i++) {
        const hidePortId = emptyDataPorts[i];
        this.__excludePort(hidePortId);
      }

      this.__addInputPortButton.setVisibility(this.__checkAddInputPortButtonVisibility());
    },
    /*
     * <-- /Dynamic inputs -->
     */

    __createLinkUnlinkStack: function(field) {
      const linkUnlinkStack = new qx.ui.container.Stack();

      const linkOptions = this.__createLinkOpts(field);
      linkUnlinkStack.add(linkOptions);

      const unlinkBtn = this.__createUnlinkButton(field);
      linkUnlinkStack.add(unlinkBtn);

      this.__linkUnlinkStackMap[field.key] = linkUnlinkStack;

      return linkUnlinkStack;
    },

    __createLinkOpts: function(field) {
      const optionsMenu = new qx.ui.menu.Menu().set({
        offsetLeft: 2,
        position: "right-top"
      });
      optionsMenu.getContentElement().setStyles({
        "border-top-right-radius": "6px",
        "border-bottom-right-radius": "6px",
        "border-bottom-left-radius": "6px"
      });
      const fieldOptsBtn = new qx.ui.form.MenuButton().set({
        menu: optionsMenu,
        icon: "@FontAwesome5Solid/link/12",
        maxHeight: 23,
        focusable: false,
        allowGrowX: false,
        alignX: "center"
      });
      this.__fieldOptsBtnMap[field.key] = fieldOptsBtn;
      // populate the button/menu when the it appears
      fieldOptsBtn.addListenerOnce("appear", () => {
        if (this.getStudy()) {
          this.__populateFieldOptionsMenu(optionsMenu, field);
          this.getStudy().getWorkbench().addListener("pipelineChanged", () => this.__populateFieldOptionsMenu(optionsMenu, field), this);
        }
      });
      return fieldOptsBtn;
    },

    __createUnlinkButton: function(field) {
      const unlinkBtn = new qx.ui.form.Button(null, "@FontAwesome5Solid/unlink/12").set({
        toolTipText: this.tr("Unlink"),
        maxHeight: 23
      });
      unlinkBtn.addListener("execute", () => this.removePortLink(field.key), this);
      return unlinkBtn;
    },

    __populateFieldOptionsMenu: function(optionsMenu, field) {
      optionsMenu.removeAll();

      this.__addInputsMenuButtons(field.key, optionsMenu);

      if (optionsMenu.getChildren().length) {
        optionsMenu.addSeparator();
      }

      const studyUI = this.getStudy().getUi();
      if (["FileButton"].includes(field.widgetType)) {
        const menuButton = this.__getSelectFileButton(field.key);
        studyUI.bind("mode", menuButton, "visibility", {
          converter: mode => mode === "workbench" ? "visible" : "excluded"
        });
        optionsMenu.add(menuButton);
      }
      if (this.self().isFieldParametrizable(field)) {
        const newParamBtn = this.__getNewParamButton(field.key);
        newParamBtn.exclude();
        optionsMenu.add(newParamBtn);
        const paramsMenuBtn = this.__getParamsMenuButton(field.key);
        paramsMenuBtn.exclude();
        optionsMenu.add(paramsMenuBtn);
        const areParamsEnabled = osparc.utils.Utils.isDevelopmentPlatform();
        [
          newParamBtn,
          paramsMenuBtn
        ].forEach(btn => {
          studyUI.bind("mode", btn, "visibility", {
            converter: mode => mode === "workbench" && areParamsEnabled ? "visible" : "excluded"
          });
        });
      }

      if (optionsMenu.getChildren().length) {
        optionsMenu.addSeparator();
      }
      const inputRequiredButton = this.__getInputRequiredButton(field.key);
      optionsMenu.add(inputRequiredButton);
    },

    __connectToInputNode: function(targetPortId, inputNodeId, outputKey) {
      this.getNode().addInputNode(inputNodeId);
      this.getNode().addPortLink(targetPortId, inputNodeId, outputKey)
        .then(connected => {
          if (connected) {
            this.getNode().fireEvent("reloadModel");
          }
        });
    },

    __addInputsMenuButtons: function(targetPortId, menu) {
      const study = this.getStudy();
      const thisNode = this.getNode();
      if (study && thisNode) {
        const inputNodeIDs = thisNode.getInputNodes();
        inputNodeIDs.forEach(inputNodeId => {
          const inputNode = this.getStudy().getWorkbench().getNode(inputNodeId);
          if (inputNode) {
            for (const outputKey in inputNode.getOutputs()) {
              const paramButton = new qx.ui.menu.Button();
              inputNode.bind("label", paramButton, "label", {
                converter: val => val + " : " + inputNode.getOutput(outputKey).label
              });
              paramButton.addListener("execute", () => this.__connectToInputNode(targetPortId, inputNodeId, outputKey), this);
              menu.add(paramButton);
              osparc.utils.Ports.arePortsCompatible(inputNode, outputKey, this.getNode(), targetPortId)
                .then(compatible => {
                  if (compatible === false) {
                    paramButton.exclude();
                  }
                });
            }
          }
        });
      }
    },

    __getInputMenuButton: function(inputNodeId, targetPortId) {
      const study = this.getStudy();
      const thisNode = this.getNode();
      if (study && thisNode) {
        const node = study.getWorkbench().getNode(inputNodeId);

        const inputNodePortsMenu = new qx.ui.menu.Menu();
        const inputMenuBtn = new qx.ui.menu.Button(null, null, null, inputNodePortsMenu);
        node.bind("label", inputMenuBtn, "label");
        if (this.getStudy()) {
          this.__populateInputNodePortsMenu(inputNodeId, targetPortId, inputNodePortsMenu, inputMenuBtn);
        }
        return inputMenuBtn;
      }
      return null;
    },

    __populateInputNodePortsMenu: function(inputNodeId, targetPortId, menu, menuBtn) {
      menuBtn.exclude();
      menu.removeAll();

      const inputNode = this.getStudy().getWorkbench().getNode(inputNodeId);
      if (inputNode) {
        for (const outputKey in inputNode.getOutputs()) {
          osparc.utils.Ports.arePortsCompatible(inputNode, outputKey, this.getNode(), targetPortId)
            .then(compatible => {
              if (compatible) {
                const paramButton = new qx.ui.menu.Button(inputNode.getOutput(outputKey).label);
                paramButton.addListener("execute", () => this.__connectToInputNode(targetPortId, inputNodeId, outputKey), this);
                menu.add(paramButton);
                menuBtn.show();
              }
            });
        }
      }
    },

    __getSelectFileButton: function(portId) {
      const selectFileButton = new qx.ui.menu.Button(this.tr("Select File"));
      selectFileButton.addListener("execute", () => this.fireDataEvent("filePickerRequested", {
        portId,
        file: null
      }), this);
      return selectFileButton;
    },

    __getNewParamButton: function(portId) {
      const newParamBtn = new qx.ui.menu.Button(this.tr("Set new parameter"));
      newParamBtn.addListener("execute", () => this.fireDataEvent("parameterRequested", portId), this);
      return newParamBtn;
    },

    __getParamsMenuButton: function(portId) {
      const existingParamMenu = new qx.ui.menu.Menu();
      const existingParamBtn = new qx.ui.menu.Button(this.tr("Set existing parameter"), null, null, existingParamMenu);
      if (this.getStudy()) {
        this.__populateExistingParamsMenu(portId, existingParamMenu, existingParamBtn);
      }
      return existingParamBtn;
    },

    __populateExistingParamsMenu: function(targetPortId, menu, menuBtn) {
      menuBtn.exclude();
      menu.removeAll();

      const params = this.getStudy().getParameters();
      params.forEach(paramNode => {
        const inputNodeId = paramNode.getNodeId();
        const outputKey = "out_1";
        osparc.utils.Ports.arePortsCompatible(paramNode, outputKey, this.getNode(), targetPortId)
          .then(compatible => {
            if (compatible) {
              const paramButton = new qx.ui.menu.Button();
              paramButton.nodeId = inputNodeId;
              paramNode.bind("label", paramButton, "label");
              paramButton.addListener("execute", () => this.__connectToInputNode(targetPortId, inputNodeId, outputKey), this);
              if (!menu.getChildren().some(child => child.nodeId === paramButton.nodeId)) {
                menu.add(paramButton);
                menuBtn.show();
              }
            }
          });
      });
    },

    __getInputRequiredButton: function(portId) {
      const node = this.getNode();
      const inputRequiredBtn = new qx.ui.menu.Button(this.tr("Required Input"));
      const evalButton = () => {
        if (node.getInputsRequired().includes(portId)) {
          inputRequiredBtn.set({
            icon: "@FontAwesome5Regular/check-square/12"
          });
        } else {
          inputRequiredBtn.set({
            icon: "@FontAwesome5Regular/square/12"
          });
        }
      }
      node.addListener("changeInputsRequired", () => evalButton(), this);
      inputRequiredBtn.addListener("execute", () => node.toggleInputRequired(portId), this);
      evalButton();
      return inputRequiredBtn;
    },

    // overridden
    addItems: function(items, names, title, itemOptions, headerOptions) {
      this.base(arguments, items, names, title, itemOptions, headerOptions);

      // header
      let row = title === null ? 0 : 1;

      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        const portId = item.key;

        const fieldOpts = this.__createLinkUnlinkStack(item);
        if (fieldOpts) {
          this._add(fieldOpts, {
            row,
            column: this.self().GRID_POS.FIELD_LINK_UNLINK
          });
        }

        this.__createDropMechanism(item, portId);

        // Notify focus and focus out
        const msgDataFn = (nodeId, pId) => this.__arePortsCompatible(nodeId, pId, this.getNode().getNodeId(), item.key);

        item.addListener("focus", () => {
          if (this.getNode()) {
            qx.event.message.Bus.getInstance().dispatchByName("inputFocus", msgDataFn);
          }
        }, this);
        item.addListener("focusout", () => {
          if (this.getNode()) {
            qx.event.message.Bus.getInstance().dispatchByName("inputFocusout", msgDataFn);
          }
        }, this);

        row++;
      }

      const evalRequired = () => {
        for (const portId in this.__ctrlLinkMap) {
          this.evalFieldRequired(portId);
        }
      }
      this.getNode().addListener("changeInputsRequired", () => evalRequired());
      evalRequired();

      // add port button
      const addPortButton = this.__addInputPortButton = new qx.ui.form.Button().set({
        label: this.tr("Input"),
        icon: "@FontAwesome5Solid/plus/14",
        marginTop: 6,
        allowGrowX: false,
        minWidth: 70
      });
      addPortButton.addListener("execute", () => this.__addInputPortButtonClicked());
      this._add(addPortButton, {
        row,
        column: this.self().GRID_POS.LABEL
      });
    },

    // overridden
    setAccessLevel: function(data) {
      const entry = this.self().GRID_POS;
      const disableables = osparc.form.renderer.PropFormBase.getDisableables();
      Object.entries(data).forEach(([portId, visibility]) => {
        Object.values(entry).forEach(entryPos => {
          const layoutElement = this._getLayoutChild(portId, entryPos);
          if (layoutElement && layoutElement.child) {
            const control = layoutElement.child;
            if (control) {
              const vis = visibility === this._visibility.hidden ? "excluded" : "visible";
              const enabled = visibility === this._visibility.readWrite;
              control.setVisibility(vis);
              if (disableables.includes(entryPos)) {
                control.setEnabled(enabled);
              }
            }
          }
        });
      });
      this.fireEvent("changeChildVisibility");
    },

    setPortErrorMessage: function(portId, msg) {
      const infoButton = this._getInfoFieldChild(portId);
      if (infoButton && "child" in infoButton) {
        const infoHint = infoButton.child;
        infoHint.setPortErrorMsg(msg);
      }
    },

    retrievingPortData: function(portId, status) {
      if (status === undefined) {
        status = this.self().RETRIEVE_STATUS.retrieving;
      }
      if (portId) {
        let data = this._getCtrlFieldChild(portId);
        if (data) {
          let child = data.child;
          let idx = data.idx;
          const layoutProps = child.getLayoutProperties();
          this.__setRetrievingStatus(status, portId, idx+1, layoutProps.row);
        }
      } else {
        for (let i = this._getChildren().length; i--;) {
          let child = this._getChildren()[i];
          const layoutProps = child.getLayoutProperties();
          if (layoutProps.column === this.self().GRID_POS.CTRL_FIELD) {
            const ctrl = this._form.getControl(child.key);
            if (ctrl && ctrl["link"]) {
              this.__setRetrievingStatus(status, child.key, i, layoutProps.row);
            }
          }
        }
      }
    },

    retrievedPortData: function(portId, succeed, dataSize = -1) {
      let status = succeed ? this.self().RETRIEVE_STATUS.succeed : this.self().RETRIEVE_STATUS.failed;
      if (parseInt(dataSize) === 0) {
        status = this.self().RETRIEVE_STATUS.empty;
      }
      if (portId) {
        let data = this._getCtrlFieldChild(portId);
        if (data) {
          let child = data.child;
          let idx = data.idx;
          const layoutProps = child.getLayoutProperties();
          this.__setRetrievingStatus(status, portId, idx+1, layoutProps.row);
        }
      } else {
        let children = this._getChildren();
        for (let i=0; i<children.length; i++) {
          let child = children[i];
          const layoutProps = child.getLayoutProperties();
          if (layoutProps.column === this.self().GRID_POS.RETRIEVE_STATUS) {
            this.__setRetrievingStatus(status, portId, i, layoutProps.row);
          }
        }
      }
    },

    __setRetrievingStatus: function(status, portId, idx, row) {
      // remove first if any
      let children = this._getChildren();
      for (let i=0; i<children.length; i++) {
        let child = children[i];
        const layoutProps = child.getLayoutProperties();
        if (layoutProps.row === row &&
          layoutProps.column === this.self().GRID_POS.RETRIEVE_STATUS) {
          this._remove(child);
        }
      }

      const label = this._getLabelFieldChild(portId).child;
      if (label && label.isVisible()) {
        const icon = this.self().getIconForStatus(status);
        icon.key = portId;
        this._addAt(icon, idx, {
          row,
          column: this.self().GRID_POS.RETRIEVE_STATUS
        });
      }
    },

    __arePortsCompatible: function(node1Id, port1Id, node2Id, port2Id) {
      return new Promise((resolve, reject) => {
        if (node1Id === node2Id) {
          resolve(false);
          return;
        }
        const workbench = this.getStudy().getWorkbench();
        const node1 = workbench.getNode(node1Id);
        const node2 = workbench.getNode(node2Id);
        if (workbench && node1 && node2) {
          osparc.utils.Ports.arePortsCompatible(node1, port1Id, node2, port2Id)
            .then(compatible => {
              resolve(compatible);
            })
            .catch(err => {
              console.error(err);
              reject(err);
            });
        } else {
          resolve(false);
        }
      });
    },

    __createDropMechanism: function(uiElement, portId) {
      if (this.getNode()) {
        uiElement.set({
          droppable: true
        });

        uiElement.addListener("dragover", e => {
          if (e.supportsType("osparc-port-link")) {
            const data = e.getData("osparc-port-link");
            const node1 = data["node1"];
            const port1Key = data["port1Key"];
            const destinations = data["destinations"];
            const port2Key = portId;

            const node2Id = this.getNode().getNodeId();
            if (!(node2Id in destinations)) {
              destinations[node2Id] = {};
            }
            if (!(port2Key in destinations[node2Id])) {
              destinations[node2Id][port2Key] = "fetching";
              osparc.utils.Ports.arePortsCompatible(node1, port1Key, this.getNode(), port2Key)
                .then(compatible => {
                  destinations[node2Id][port2Key] = compatible;
                });
            }

            const compatible = destinations[node2Id][portId];
            if (compatible) {
              // stop propagation, so that the form doesn't attend it (and preventDefault it)
              e.stopPropagation();
              this.__highlightCompatibles(portId);
            }
          }

          if (e.supportsType("osparc-file-link")) {
            const data = e.getData("osparc-file-link");
            if ("dragData" in data && "type" in uiElement) {
              const compatible = uiElement.type.includes("data:");
              if (compatible) {
                // stop propagation, so that the form doesn't attend it (and preventDefault it)
                e.stopPropagation();
                this.__highlightCompatibles(portId);
              }
            }
          }
        }, this);

        uiElement.addListener("drop", e => {
          if (e.supportsType("osparc-port-link")) {
            const port2Key = portId;
            const data = e.getData("osparc-port-link");
            const node1Id = data["node1"].getNodeId();
            const port1Key = data["port1Key"];
            this.getNode().addPortLink(port2Key, node1Id, port1Key);
          }
          if (e.supportsType("osparc-file-link")) {
            const data = e.getData("osparc-file-link");
            this.fireDataEvent("filePickerRequested", {
              portId,
              file: {
                data: data["dragData"]
              }
            });
          }
        }, this);
      }
    },

    __highlightCompatibles: function(compatiblePorts) {
      this._getChildren().forEach(child => {
        if ("key" in child && compatiblePorts.includes(child.key)) {
          child.setDecorator("material-textfield-focused");
        }
      });
    },

    __unhighlightAll: function() {
      this._getChildren().forEach(child => {
        if ("key" in child) {
          child.resetDecorator();
        }
      });
    },

    __attachDragoverHighlighter: function() {
      this.addListener("dragover", e => {
        if (e.supportsType("osparc-port-link")) {
          const data = e.getData("osparc-port-link");
          const node1 = data["node1"];
          const dragPortId = data["port1Key"];

          const destinations = data["destinations"];
          const node2Id = this.getNode().getNodeId();
          if (!(node2Id in destinations)) {
            destinations[node2Id] = {};
          }
          this.getPortIds().forEach(portId => {
            if (!(portId in destinations[node2Id])) {
              destinations[node2Id][portId] = "fetching";
            }
          });
          osparc.data.Resources.getCompatibleInputs(node1, dragPortId, this.getNode())
            .then(compatiblePorts => {
              this.getPortIds().forEach(portId => {
                destinations[node2Id][portId] = compatiblePorts.includes(portId);
              });
              this.__highlightCompatibles(compatiblePorts);
            })
            .catch(err => {
              console.error(err);
            });

          e.preventDefault();
        }
      }, this);
      this.addListener("dragleave", e => {
        if (e.supportsType("osparc-port-link")) {
          this.__unhighlightAll();
        }
      }, this);
      this.addListener("mouseup", e => {
        this.__unhighlightAll();
      });
    },

    __isPortAvailable: function(portId) {
      const port = this._form.getControl(portId);
      if (!port ||
        !port.getEnabled() ||
        Object.prototype.hasOwnProperty.call(port, "link") ||
        Object.prototype.hasOwnProperty.call(port, "parameter")) {
        return false;
      }
      return true;
    },

    __createFieldCtrl: function(portId) {
      const controlParam = new qx.ui.form.TextField().set({
        enabled: false
      });
      controlParam.key = portId;
      return controlParam;
    },

    __resetCtrlField: function(portId) {
      let data = this._getCtrlFieldChild(portId);
      if (data) {
        const {child, idx} = data;
        const layoutProps = child.getLayoutProperties();
        if (layoutProps.column === this.self().GRID_POS.CTRL_FIELD) {
          this._remove(child);
          const item = this._form.getControl(portId);
          item.show();
          this._addAt(item, idx, {
            row: layoutProps.row,
            column: this.self().GRID_POS.CTRL_FIELD
          });

          return true;
        }
      }
      return false;
    },

    getPortIds: function() {
      return Object.keys(this._form.getControls());
    },

    /* LINKS */
    getControlLink: function(portId) {
      return this.__ctrlLinkMap[portId];
    },

    __addLinkCtrl: function(portId) {
      const controlLink = this.__createFieldCtrl(portId);
      this.__ctrlLinkMap[portId] = controlLink;
    },

    __addLinkCtrls: function() {
      this.getPortIds().forEach(portId => {
        this.__addLinkCtrl(portId);
      });
    },

    __portLinkAdded: function(portId, fromNodeId, fromPortId) {
      let data = this._getCtrlFieldChild(portId);
      if (data) {
        let child = data.child;
        const idx = data.idx;
        const layoutProps = child.getLayoutProperties();
        this._remove(child);

        const ctrlLink = this.getControlLink(portId);
        ctrlLink.setEnabled(false);
        ctrlLink.key = portId;
        this._addAt(ctrlLink, idx, {
          row: layoutProps.row,
          column: this.self().GRID_POS.CTRL_FIELD
        });

        if (portId in this.__linkUnlinkStackMap) {
          const stack = this.__linkUnlinkStackMap[portId];
          if (stack.getSelectables().length > 1) {
            stack.setSelection([stack.getSelectables()[1]]);
          }
        }

        const linkFieldModified = {
          portId,
          fromNodeId,
          fromPortId,
          added: true
        };
        this.fireDataEvent("linkFieldModified", linkFieldModified);
      }
    },

    __portLinkRemoved: function(portId) {
      if (this.__resetCtrlField(portId)) {
        if (portId in this.__linkUnlinkStackMap) {
          const stack = this.__linkUnlinkStackMap[portId];
          if (stack.getSelectables().length > 0) {
            stack.setSelection([stack.getSelectables()[0]]);
          }
        }

        const linkFieldModified = {
          portId,
          added: false
        };
        this.fireDataEvent("linkFieldModified", linkFieldModified);
      }
    },

    getLink: function(portId) {
      if ("link" in this._form.getControl(portId)) {
        return this._form.getControl(portId)["link"];
      }
      return null;
    },

    getLinks: function() {
      const links = [];
      Object.keys(this.__ctrlLinkMap).forEach(portId => {
        const link = this.getLink(portId);
        if (link) {
          links.push(link);
        }
      });
      return links;
    },

    addPortLink: function(toPortId, fromNodeId, fromPortId) {
      const study = this.getStudy();
      if (!study) {
        return null;
      }
      if (!this.__isPortAvailable(toPortId)) {
        return false;
      }
      const ctrlLink = this.getControlLink(toPortId);
      ctrlLink.setEnabled(false);
      this._form.getControl(toPortId)["link"] = {
        nodeUuid: fromNodeId,
        output: fromPortId
      };
      const highlightEdgeUI = highlight => {
        this.fireDataEvent("highlightEdge", {
          highlight,
          toNodeId: this.getNode().getNodeId(),
          toPortId,
          fromNodeId,
          fromPortId,
        });
      };
      ctrlLink.addListener("mouseover", () => highlightEdgeUI(true));
      ctrlLink.addListener("mouseout", () => highlightEdgeUI(false));

      const workbench = study.getWorkbench();
      const fromNode = workbench.getNode(fromNodeId);
      const port = fromNode.getOutput(fromPortId);
      const fromPortLabel = port ? port.label : null;
      fromNode.bind("label", ctrlLink, "value", {
        converter: label => label + ": " + fromPortLabel
      });
      // Hack: Show tooltip if element is disabled
      const addToolTip = () => {
        ctrlLink.getContentElement().removeAttribute("title");
        const toolTipText = fromNode.getLabel() + ":\n" + fromPortLabel;
        ctrlLink.getContentElement().setAttribute("title", toolTipText);
      };
      fromNode.addListener("changeLabel", () => addToolTip());
      addToolTip();

      this.__portLinkAdded(toPortId, fromNodeId, fromPortId);

      this.makeInputsDynamic();

      return true;
    },

    setInputLinks: function(inputLinks) {
      for (let key in inputLinks) {
        if (osparc.utils.Ports.isDataALink(inputLinks[key])) {
          this.addPortLink(key, inputLinks[key].nodeUuid, inputLinks[key].output);
        }
      }
    },

    removePortLink: function(toPortId) {
      this.getControlLink(toPortId).setEnabled(false);
      if ("link" in this._form.getControl(toPortId)) {
        delete this._form.getControl(toPortId)["link"];
      }

      this.__portLinkRemoved(toPortId);
    }
    /* /LINKS */
  }
});
