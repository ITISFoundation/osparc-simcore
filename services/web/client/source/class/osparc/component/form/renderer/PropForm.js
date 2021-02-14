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
   * @param form {osparc.component.form.Auto} form widget to embedd
   * @param node {osparc.data.model.Node} Node owning the widget
   */
  construct: function(form, node) {
    this.base(arguments, form, node);

    this.__ctrlLinkMap = {};
    this.__addLinkCtrls();

    this.__ctrlParamMap = {};
    this.__addParamCtrls();

    this.setDroppable(true);
    this.__attachDragoverHighlighter();
  },

  events: {
    "linkFieldModified": "qx.event.type.Data",
    "changeChildVisibility": "qx.event.type.Event"
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
    }
  },

  // eslint-disable-next-line qx-rules/no-refs-in-members
  members: {
    // overridden
    _gridPos: {
      label: 0,
      info: 1,
      ctrlField: 2,
      unit: 3,
      retrieveStatus: 4
    },

    _retrieveStatus: {
      failed: -1,
      empty: 0,
      retrieving: 1,
      succeed: 2
    },

    __ctrlLinkMap: null,

    // overridden
    addItems: function(items, names, title, itemOptions, headerOptions) {
      this.base(arguments, items, names, title, itemOptions, headerOptions);

      items.forEach(item => {
        this.__createDropMechanism(item, item.portId);

        // Notify focus and focus out
        const msgDataFn = (nodeId, portId) => this.__arePortsCompatible(nodeId, portId, this.getNode().getNodeId(), item.portId);

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
      });
    },

    // overridden
    setAccessLevel: function(data) {
      for (const key in data) {
        const label = this._getLabelFieldChild(key);
        if (label) {
          this.__changeControlVisibility(label.child, data[key]);
        }

        const info = this._getInfoFieldChild(key);
        if (info) {
          this.__changeControlVisibility(info.child, data[key]);
        }

        const controlLink = this._getCtrlFieldChild(key);
        if (controlLink) {
          this.__changeControlVisibility(controlLink.child, data[key]);
        }

        const retrieveField = this.__getRetrieveFieldChild(key);
        if (retrieveField) {
          this.__changeControlVisibility(retrieveField.child, data[key]);
        }

        this.fireEvent("changeChildVisibility");
      }
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
          if (layoutProps.column === this._gridPos.ctrlField) {
            const ctrl = this._form.getControl(child.portId);
            if (ctrl && ctrl["link"]) {
              this.__setRetrievingStatus(status, child.portId, i, layoutProps.row);
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
          if (layoutProps.column === this._gridPos.retrieveStatus) {
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
      icon.portId = portId;

      // remove first if any
      let children = this._getChildren();
      for (let i=0; i<children.length; i++) {
        let child = children[i];
        const layoutProps = child.getLayoutProperties();
        if (layoutProps.row === row &&
          layoutProps.column === this._gridPos.retrieveStatus) {
          this._remove(child);
        }
      }

      this._addAt(icon, idx, {
        row: row,
        column: this._gridPos.retrieveStatus
      });
    },

    __arePortsCompatible: function(node1Id, port1Id, node2Id, port2Id) {
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const workbench = study.getWorkbench();
      if (workbench && node1Id && node2Id) {
        const node1 = workbench.getNode(node1Id);
        const node2 = workbench.getNode(node2Id);
        if (node1 && node2) {
          const port1 = node1.getOutput(port1Id);
          const port2 = node2.getInput(port2Id);
          return osparc.utils.Ports.arePortsCompatible(port1, port2);
        }
      }
      return false;
    },

    __createDropMechanism: function(uiElement, portId) {
      if (this.getNode()) {
        uiElement.set({
          droppable: true
        });
        uiElement.node = this.getNode();
        uiElement.portId = portId;

        uiElement.addListener("dragover", e => {
          if (e.supportsType("osparc-port-link")) {
            const from = e.getRelatedTarget();
            let dragNodeId = from.node.getNodeId();
            let dragPortId = from.portId;
            const to = e.getCurrentTarget();
            let dropNodeId = to.node.getNodeId();
            let dropPortId = to.portId;
            if (this.__arePortsCompatible(dragNodeId, dragPortId, dropNodeId, dropPortId)) {
              e.stopPropagation();
            } else {
              e.preventDefault();
            }
          }
        }, this);

        uiElement.addListener("drop", e => {
          if (e.supportsType("osparc-port-link")) {
            const from = e.getRelatedTarget();
            let dragNodeId = from.nodeId;
            let dragPortId = from.portId;
            const to = e.getCurrentTarget();
            // let dropNodeId = to.nodeId;
            let dropPortId = to.portId;
            this.getNode().addPortLink(dropPortId, dragNodeId, dragPortId);
          }
        }, this);
      }
    },

    __getCompatibleInputs: function(output) {
      return this._getChildren().filter(child => child.getField && this.__arePortsCompatible(output.nodeId, output.portId, child.getField().nodeId, child.getField().portId));
    },

    __highlightCompatibles: function(output) {
      /*
      const inputs = this.__getCompatibleInputs(output);
      for (let i in inputs) {
        const input = inputs[i].getField();
        input.setDecorator("material-textfield-focused");
      }
      */
      osparc.utils.Ports.getCompatiblePorts(output.node, output.portId, this.getNode())
        .then(compatiblePorts => {
          console.log(compatiblePorts);
          this._getChildren().forEach(child => {
            if (child.getField && compatiblePorts.includes(child.getField().portId)) {
              const input = child.getField();
              input.setDecorator("material-textfield-focused");
            }
          });
        })
        .catch(err => {
          console.error(err);
        });
    },

    __unhighlightAll: function() {
      const inputs = this._getChildren().filter(child => child.getField);
      for (let i in inputs) {
        const input = inputs[i];
        input.getField().resetDecorator();
      }
    },

    __attachDragoverHighlighter: function() {
      this.addListener("dragover", e => {
        if (e.supportsType("osparc-port-link")) {
          this.__highlightCompatibles(e.getRelatedTarget());
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
      controlParam.portId = portId;
      return controlParam;
    },

    __resetCtrlField: function(portId) {
      let data = this._getCtrlFieldChild(portId);
      if (data) {
        const {child, idx} = data;
        const layoutProps = child.getLayoutProperties();
        if (layoutProps.column === this._gridPos.ctrlField) {
          this._remove(child);
          const item = this._form.getControl(portId);

          const field = this._createFieldWithMenu(item);
          this._addAt(field, idx, {
            row: layoutProps.row,
            column: this._gridPos.ctrlField
          });
          return true;
        }
      }
      return false;
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
      Object.keys(this._form.getControls()).forEach(portId => {
        this.__addLinkCtrl(portId);
      });
    },

    __linkAdded: function(portId, fromNodeId, fromPortId) {
      let data = this._getCtrlFieldChild(portId);
      if (data) {
        let child = data.child;
        const idx = data.idx;
        const layoutProps = child.getLayoutProperties();
        this._remove(child);

        const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));

        const unlinkBtn = new qx.ui.form.Button(this.tr("Unlink"), "@FontAwesome5Solid/unlink/14");
        unlinkBtn.addListener("execute", function() {
          this.removeLink(portId);
        }, this);
        hBox.add(unlinkBtn);

        hBox.add(this.getControlLink(portId), {
          flex: 1
        });

        hBox.portId = portId;

        this._addAt(hBox, idx, {
          row: layoutProps.row,
          column: this._gridPos.ctrlField
        });

        const linkFieldModified = {
          portId,
          fromNodeId,
          fromPortId,
          added: true
        };
        this.fireDataEvent("linkFieldModified", linkFieldModified);
      }
    },

    __linkRemoved: function(portId) {
      if (this.__resetCtrlField(portId)) {
        const linkFieldModified = {
          portId,
          added: false
        };
        this.fireDataEvent("linkFieldModified", linkFieldModified);
      }
    },

    getLinks: function() {
      const links = [];
      Object.keys(this.__ctrlLinkMap).forEach(portKey => {
        if ("link" in this._form.getControl(portKey)) {
          links.push(this._form.getControl(portKey)["link"]);
        }
      });
      return links;
    },

    addLink: function(toPortId, fromNodeId, fromPortId) {
      if (!this.__isPortAvailable(toPortId)) {
        return false;
      }
      this.getControlLink(toPortId).setEnabled(false);
      this._form.getControl(toPortId)["link"] = {
        nodeUuid: fromNodeId,
        output: fromPortId
      };

      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const workbench = study.getWorkbench();
      const fromNode = workbench.getNode(fromNodeId);
      const port = fromNode.getOutput(fromPortId);
      const fromPortLabel = port ? port.label : null;
      fromNode.bind("label", this.getControlLink(toPortId), "value", {
        converter: label => label + ": " + fromPortLabel
      });

      this.__linkAdded(toPortId, fromNodeId, fromPortId);

      return true;
    },

    addLinks: function(data) {
      for (let key in data) {
        if (osparc.utils.Ports.isDataALink(data[key])) {
          this.addLink(key, data[key].nodeUuid, data[key].output);
        }
      }
    },

    removeLink: function(toPortId) {
      this.getControlLink(toPortId).setEnabled(false);
      if ("link" in this._form.getControl(toPortId)) {
        delete this._form.getControl(toPortId)["link"];
      }

      this.__linkRemoved(toPortId);
    },
    /* /LINKS */

    /* PARAMETERS */
    getControlParam: function(key) {
      return this.__ctrlParamMap[key];
    },

    __addParamCtrl: function(portId) {
      const controlParam = this.__createFieldCtrl(portId);
      this.__ctrlParamMap[portId] = controlParam;
    },

    __addParamCtrls: function() {
      Object.keys(this._form.getControls()).forEach(portId => {
        this.__addParamCtrl(portId);
      });
    },

    __parameterAdded: function(portId) {
      let data = this._getCtrlFieldChild(portId);
      if (data) {
        let child = data.child;
        const idx = data.idx;
        const layoutProps = child.getLayoutProperties();
        this._remove(child);

        const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
        hBox.add(this.getControlParam(portId), {
          flex: 1
        });

        const unparamBtn = new qx.ui.form.Button(this.tr("Remove parameter"), "@FontAwesome5Solid/unlink/14");
        unparamBtn.addListener("execute", function() {
          this.removeParameter(portId);
        }, this);
        hBox.add(unparamBtn);

        hBox.portId = portId;

        this._addAt(hBox, idx, {
          row: layoutProps.row,
          column: this._gridPos.ctrlField
        });
      }
    },

    __parameterRemoved: function(portId) {
      this.__resetCtrlField(portId);
    },

    // overridden
    addParameter: function(portId, parameter) {
      if (!this.__isPortAvailable(portId)) {
        return false;
      }
      if (!parameter) {
        return false;
      }

      this.getControlParam(portId).setEnabled(false);
      this._form.getControl(portId).parameter = parameter;
      // ToDo: Binding missing
      this.getControlParam(portId).setValue(this.tr("Parameter: ") + parameter.label);
      this.__parameterAdded(portId);
      return true;
    },

    addParameters: function(data) {
      for (let key in data) {
        if (osparc.utils.Ports.isDataAParameter(data[key])) {
          const parameterId = data[key].replace("{{", "").replace("}}", "");
          const study = osparc.store.Store.getInstance().getCurrentStudy();
          const parameter = study.getSweeper().getParameter(parameterId);
          if (parameter) {
            this.addParameter(key, parameter);
          }
        }
      }
    },

    removeParameter: function(portId) {
      this.getControlParam(portId).setEnabled(false);
      let ctrlField = this._form.getControl(portId);
      if (ctrlField && "parameter" in ctrlField) {
        delete ctrlField.parameter;
      }

      this.__parameterRemoved(portId);
    },
    /* /PARAMETERS */

    __changeControlVisibility: function(control, visibility) {
      if (control === null) {
        return;
      }

      switch (visibility) {
        case this._visibility.hidden:
          control.setEnabled(false);
          control.setVisibility("excluded");
          break;
        case this._visibility.readOnly:
          control.setEnabled(false);
          control.setVisibility("visible");
          break;
        case this._visibility.readWrite:
          control.setEnabled(true);
          control.setVisibility("visible");
          break;
      }
    },

    __getRetrieveFieldChild: function(portId) {
      return this._getLayoutChild(portId, this._gridPos.retrieveStatus);
    }
  }
});
