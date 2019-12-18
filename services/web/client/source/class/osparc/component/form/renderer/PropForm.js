/* ************************************************************************
   Copyright: 2013 OETIKER+PARTNER AG
              2018 ITIS Foundation
   License:   MIT
   Authors:   Tobi Oetiker <tobi@oetiker.ch>
   Utf8Check: äöü
************************************************************************ */

/* eslint no-underscore-dangle: ["error", { "allowAfterThis": true, "allow": ["__ctrlMap"] }] */

/**
 * A special renderer for AutoForms which includes notes below the section header
 * widget and next to the individual form widgets.
 */

qx.Class.define("osparc.component.form.renderer.PropForm", {
  extend : qx.ui.form.renderer.Single,
  /**
     * create a page for the View Tab with the given title
     *
     * @param vizWidget {Widget} visualization widget to embedd
     */
  construct: function(form, workbench, node) {
    // workbench and node are necessary for creating links
    if (workbench) {
      this.setWorkbench(workbench);
    } else {
      this.setWorkbench(null);
    }
    if (node) {
      this.setNode(node);
    } else {
      this.setNode(null);
    }

    this.base(arguments, form);
    let fl = this._getLayout();
    // have plenty of space for input, not for the labels
    fl.setColumnFlex(0, 0);
    fl.setColumnAlign(0, "left", "top");
    fl.setColumnFlex(1, 1);
    fl.setColumnMinWidth(1, 130);

    this.setDroppable(true);
    this.__attachDragoverHighlighter();
  },

  events: {
    "removeLink" : "qx.event.type.Data",
    "dataFieldModified": "qx.event.type.Data"
  },

  properties: {
    workbench: {
      check: "osparc.data.model.Workbench",
      nullable: true
    },

    node: {
      check: "osparc.data.model.Node",
      nullable: true
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
    }
  },

  // eslint-disable-next-line qx-rules/no-refs-in-members
  members: {
    _gridPos: {
      label: 0,
      entryField: 1,
      retrieveStatus: 2
    },
    _retrieveStatus: {
      failed: -1,
      empty: 0,
      retrieving: 1,
      succeed: 2
    },
    addItems: function(items, names, title, itemOptions, headerOptions) {
      // add the header
      if (title !== null) {
        this._add(
          this._createHeader(title), {
            row: this._row,
            column: this._gridPos.label,
            colSpan: Object.keys(this._gridPos).length
          }
        );
        this._row++;
      }

      // add the items
      for (let i = 0; i < items.length; i++) {
        let item = items[i];
        let label = this._createLabel(names[i], item);
        this._add(label, {
          row: this._row,
          column: this._gridPos.label
        });
        label.setBuddy(item);

        const field = new osparc.component.form.FieldWHint(null, item.description, item);
        field.key = item.key;
        this._add(field, {
          row: this._row,
          column: this._gridPos.entryField
        });
        this._row++;
        this._connectVisibility(item, label);
        // store the names for translation
        if (qx.core.Environment.get("qx.dynlocale")) {
          this._names.push({
            name: names[i],
            label: label,
            item: items[i]
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
      }
    },

    getValues: function() {
      let data = this._form.getData();
      for (const portId in data) {
        let ctrl = this._form.getControl(portId);
        if (ctrl && ctrl.link) {
          if (this.getNode().getKey()
            .includes("/neuroman")) {
            // HACK: Only Neuroman should enter here
            data[portId] = ctrl.link["output"];
          } else {
            data[portId] = ctrl.link;
          }
        }
        // FIXME: "null" should be a valid input
        if (data[portId] === "null") {
          data[portId] = null;
        }
      }
      let filteredData = {};
      for (const key in data) {
        if (data[key] !== null) {
          filteredData[key] = data[key];
        }
      }
      return filteredData;
    },

    __getLayoutChild(portId, column) {
      let row = null;
      const children = this._getChildren();
      for (let i=0; i<children.length; i++) {
        const child = children[i];
        const layoutProps = child.getLayoutProperties();
        if (layoutProps.column === this._gridPos.label &&
          child.getBuddy().key === portId) {
          row = layoutProps.row;
          break;
        }
      }
      if (row !== null) {
        for (let i=0; i<children.length; i++) {
          const child = children[i];
          const layoutProps = child.getLayoutProperties();
          if (layoutProps.column === column &&
            layoutProps.row === row) {
            return {
              child,
              idx: i
            };
          }
        }
      }
      return null;
    },

    __getEntryFieldChild(portId) {
      return this.__getLayoutChild(portId, this._gridPos.entryField);
    },

    __getRetrieveStatusChild(portId) {
      return this.__getLayoutChild(portId, this._gridPos.retrieveStatus);
    },

    linkAdded: function(portId) {
      let data = this.__getEntryFieldChild(portId);
      if (data) {
        let child = data.child;
        let idx = data.idx;
        const layoutProps = child.getLayoutProperties();
        this._remove(child);

        const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
        hBox.add(this._form.getControlLink(portId), {
          flex: 1
        });

        const unlinkBtn = new qx.ui.form.Button(this.tr("Unlink"), "@FontAwesome5Solid/unlink/14");
        unlinkBtn.addListener("execute", function() {
          this.fireDataEvent("removeLink", portId);
        }, this);
        hBox.add(unlinkBtn);

        hBox.key = portId;
        this._addAt(hBox, idx, {
          row: layoutProps.row,
          column: this._gridPos.entryField
        });

        this.fireDataEvent("dataFieldModified", portId);
      }
    },

    linkRemoved: function(portId) {
      let data = this.__getEntryFieldChild(portId);
      if (data) {
        let child = data.child;
        let idx = data.idx;
        const layoutProps = child.getLayoutProperties();
        if (layoutProps.column === this._gridPos.entryField) {
          this._remove(child);
          const field = new osparc.component.form.FieldWHint(null, this._form.getControl(portId).description, this._form.getControl(portId));
          this._addAt(field, idx, {
            row: layoutProps.row,
            column: layoutProps.column
          });

          this.fireDataEvent("dataFieldModified", portId);
        }
      }
    },

    retrievingPortData: function(portId) {
      const status = this._retrieveStatus.retrieving;
      if (portId) {
        let data = this.__getEntryFieldChild(portId);
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
          if (layoutProps.column === this._gridPos.entryField) {
            const ctrl = this._form.getControl(child.key);
            if (ctrl && ctrl.link) {
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
        let data = this.__getEntryFieldChild(portId);
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
          icon = osparc.component.form.renderer.PropForm.getRetrievedAtom(false);
          break;
        case this._retrieveStatus.empty:
          icon = osparc.component.form.renderer.PropForm.getRetrievedEmpty();
          break;
        case this._retrieveStatus.retrieving:
          icon = osparc.component.form.renderer.PropForm.getRetrievingAtom();
          break;
        case this._retrieveStatus.succeed:
          icon = osparc.component.form.renderer.PropForm.getRetrievedAtom(true);
          break;
      }
      icon.key = portId;

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

    __isInputData: function(portId) {
      const port = this.getNode().getInput(portId);
      if (port) {
        return port.type.includes("data");
      }
      return false;
    },

    __arePortsCompatible: function(node1Id, port1Id, node2Id, port2Id) {
      if (this.getWorkbench() && node1Id && node2Id) {
        const node1 = this.getWorkbench().getNode(node1Id);
        const node2 = this.getWorkbench().getNode(node2Id);
        if (node1 && node2) {
          const port1 = node1.getOutput(port1Id);
          const port2 = node2.getInput(port2Id);
          return osparc.utils.Services.arePortsCompatible(port1, port2);
        }
      }
      return false;
    },

    __createDropMechanism: function(uiElement, portId) {
      if (this.getNode()) {
        uiElement.set({
          droppable: true
        });
        uiElement.nodeId = this.getNode().getNodeId();
        uiElement.portId = portId;

        uiElement.addListener("dragover", e => {
          if (e.supportsType("osparc-port-link")) {
            const from = e.getRelatedTarget();
            let dragNodeId = from.nodeId;
            let dragPortId = from.portId;
            const to = e.getCurrentTarget();
            let dropNodeId = to.nodeId;
            let dropPortId = to.portId;
            if (this.__arePortsCompatible(dragNodeId, dragPortId, dropNodeId, dropPortId)) {
              this.__highlightCompatibles(e.getRelatedTarget());
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
      const inputs = this.__getCompatibleInputs(output);
      for (let i in inputs) {
        const input = inputs[i].getField();
        input.setDecorator("material-textfield-focused");
      }
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
    }
  }
});
