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

qx.Class.define("osparc.component.form.renderer.PropForm", {
  extend: osparc.component.form.renderer.PropFormBase,

  /**
   * @param form {osparc.component.form.Auto} form widget to embed
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

    getRetrievedAtom: function(success) {
      const icon = success ? "@FontAwesome5Solid/check/12" : "@FontAwesome5Solid/times/12";
      return new qx.ui.basic.Atom("", icon);
    },

    getRetrievedEmpty: function() {
      const icon = "@FontAwesome5Solid/dot-circle/10";
      return new qx.ui.basic.Atom("", icon);
    },

    gridPos: {
      ...osparc.component.form.renderer.PropFormBase.gridPos,
      retrieveStatus: Object.keys(osparc.component.form.renderer.PropFormBase.gridPos).length
    },

    isFieldParametrizable: function(field) {
      const supportedTypes = [];
      const paramsMD = osparc.utils.Services.getParametersMetadata();
      paramsMD.forEach(paramMD => {
        supportedTypes.push(osparc.component.node.ParameterEditor.getParameterOutputTypeFromMD(paramMD));
      });
      return supportedTypes.includes(field.type);
    }
  },

  // eslint-disable-next-line qx-rules/no-refs-in-members
  members: {
    _retrieveStatus: {
      failed: -1,
      empty: 0,
      retrieving: 1,
      succeed: 2
    },

    __ctrlLinkMap: null,
    __linkUnlinkStackMap: null,
    __fieldOptsBtnMap: null,

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
        height: 23,
        focusable: false,
        allowGrowX: false,
        alignX: "center"
      });
      this.__fieldOptsBtnMap[field.key] = fieldOptsBtn;
      // populaten the button/menu when the it appears
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
        height: 23
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
        osparc.utils.Utils.isDevelopmentPlatform()
          .then(areParamsEnabled => {
            [
              newParamBtn,
              paramsMenuBtn
            ].forEach(btn => {
              studyUI.bind("mode", btn, "visibility", {
                converter: mode => mode === "workbench" && areParamsEnabled ? "visible" : "excluded"
              });
            });
          });
      }
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
              paramButton.addListener("execute", () => {
                this.getNode().addInputNode(inputNodeId);
                this.getNode().addPortLink(targetPortId, inputNodeId, outputKey);
              }, this);
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

    __getSelectFileButton: function(portId) {
      const selectFileButton = new qx.ui.menu.Button(this.tr("Select File"));
      // selectFileButton.addListener("execute", () => this.fireDataEvent("fileRequested", portId), this);
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
                paramButton.addListener("execute", () => {
                  this.getNode().addInputNode(inputNodeId);
                  this.getNode().addPortLink(targetPortId, inputNodeId, outputKey);
                }, this);
                menu.add(paramButton);
                menuBtn.show();
              }
            });
        }
      }
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
              paramButton.addListener("execute", () => {
                this.getNode().addInputNode(inputNodeId);
                this.getNode().addPortLink(targetPortId, inputNodeId, outputKey);
              }, this);
              if (!menu.getChildren().some(child => child.nodeId === paramButton.nodeId)) {
                menu.add(paramButton);
                menuBtn.show();
              }
            }
          });
      });
    },

    // overridden
    addItems: function(items, names, title, itemOptions, headerOptions) {
      this.base(arguments, items, names, title, itemOptions, headerOptions);

      // header
      let row = title === null ? 0 : 1;

      for (let i = 0; i < items.length; i++) {
        const item = items[i];

        const fieldOpts = this.__createLinkUnlinkStack(item);
        if (fieldOpts) {
          this._add(fieldOpts, {
            row,
            column: this.self().gridPos.fieldLinkUnlink
          });
        }

        this.__createDropMechanism(item, item.key);

        // Notify focus and focus out
        const msgDataFn = (nodeId, portId) => this.__arePortsCompatible(nodeId, portId, this.getNode().getNodeId(), item.key);

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
    },

    // overridden
    setAccessLevel: function(data) {
      const entry = this.self().gridPos;
      const disableables = osparc.component.form.renderer.PropFormBase.getDisableables();
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

    retrievingPortData: function(portId) {
      const status = this._retrieveStatus.retrieving;
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
          if (layoutProps.column === this.self().gridPos.ctrlField) {
            const ctrl = this._form.getControl(child.key);
            if (ctrl && ctrl["link"]) {
              this.__setRetrievingStatus(status, child.key, i, layoutProps.row);
            }
          }
        }
      }
    },

    retrievedPortData: function(portId, succeed, dataSize = -1) {
      let status = succeed ? this._retrieveStatus.succeed : this._retrieveStatus.failed;
      if (parseInt(dataSize) === 0) {
        status = this._retrieveStatus.empty;
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
          if (layoutProps.column === this.self().gridPos.retrieveStatus) {
            this.__setRetrievingStatus(status, portId, i, layoutProps.row);
          }
        }
      }
    },

    __setRetrievingStatus: function(status, portId, idx, row) {
      let icon;
      switch (status) {
        case this._retrieveStatus.failed:
          icon = this.self().getRetrievedAtom(false);
          break;
        case this._retrieveStatus.empty:
          icon = this.self().getRetrievedEmpty();
          break;
        case this._retrieveStatus.retrieving:
          icon = this.self().getRetrievingAtom();
          break;
        case this._retrieveStatus.succeed:
          icon = this.self().getRetrievedAtom(true);
          break;
      }
      icon.key = portId;

      // remove first if any
      let children = this._getChildren();
      for (let i=0; i<children.length; i++) {
        let child = children[i];
        const layoutProps = child.getLayoutProperties();
        if (layoutProps.row === row &&
          layoutProps.column === this.self().gridPos.retrieveStatus) {
          this._remove(child);
        }
      }

      this._addAt(icon, idx, {
        row: row,
        column: this.self().gridPos.retrieveStatus
      });
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
          this.__getPortKeys().forEach(portKey => {
            if (!(portKey in destinations[node2Id])) {
              destinations[node2Id][portKey] = "fetching";
            }
          });
          osparc.data.Resources.getCompatibleInputs(node1, dragPortId, this.getNode())
            .then(compatiblePorts => {
              this.__getPortKeys().forEach(portKey => {
                destinations[node2Id][portKey] = compatiblePorts.includes(portKey);
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
        if (layoutProps.column === this.self().gridPos.ctrlField) {
          this._remove(child);
          const item = this._form.getControl(portId);

          this._addAt(item, idx, {
            row: layoutProps.row,
            column: this.self().gridPos.ctrlField
          });

          return true;
        }
      }
      return false;
    },

    __getPortKeys: function() {
      return Object.keys(this._form.getControls());
    },

    /* LINKS */
    getControlLink: function(key) {
      return this.__ctrlLinkMap[key];
    },

    __addLinkCtrl: function(portId) {
      const controlLink = this.__createFieldCtrl(portId);
      this.__ctrlLinkMap[portId] = controlLink;
    },

    __addLinkCtrls: function() {
      this.__getPortKeys().forEach(portId => {
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
          column: this.self().gridPos.ctrlField
        });

        if (portId in this.__linkUnlinkStackMap) {
          const stack = this.__linkUnlinkStackMap[portId];
          stack.setSelection([stack.getSelectables()[1]]);
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
          stack.setSelection([stack.getSelectables()[0]]);
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
      this.getControlLink(toPortId).setEnabled(false);
      this._form.getControl(toPortId)["link"] = {
        nodeUuid: fromNodeId,
        output: fromPortId
      };

      const workbench = study.getWorkbench();
      const fromNode = workbench.getNode(fromNodeId);
      const port = fromNode.getOutput(fromPortId);
      const fromPortLabel = port ? port.label : null;
      fromNode.bind("label", this.getControlLink(toPortId), "value", {
        converter: label => label + ": " + fromPortLabel
      });

      this.__portLinkAdded(toPortId, fromNodeId, fromPortId);

      return true;
    },

    addPortLinks: function(data) {
      for (let key in data) {
        if (osparc.utils.Ports.isDataALink(data[key])) {
          this.addPortLink(key, data[key].nodeUuid, data[key].output);
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
