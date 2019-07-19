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

qx.Class.define("qxapp.component.form.renderer.PropForm", {
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
      check: "qxapp.data.model.Workbench",
      nullable: true
    },

    node: {
      check: "qxapp.data.model.Node",
      nullable: true
    }
  },

  // eslint-disable-next-line qx-rules/no-refs-in-members
  members: {
    _gridPos: {
      label: 0,
      entryField: 1,
      retrieveStatus: 2
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
        this._add(new qxapp.component.form.FieldWHint(null, item.description, item), {
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

    linkAdded: function(portId) {
      let children = this._getChildren();
      for (let i=0; i<children.length; i++) {
        let child = children[i];
        if (child.getField && child.getField().key === portId) {
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
          this._addAt(hBox, i, {
            row: layoutProps.row,
            column: this._gridPos.entryField
          });

          this.__retrievePortData(portId, i, layoutProps.row);
        }
      }
    },

    linkRemoved: function(portId) {
      let children = this._getChildren();
      for (let i=0; i<children.length; i++) {
        let child = children[i];
        if ("key" in child && child.key === portId) {
          const layoutProps = child.getLayoutProperties();
          if (layoutProps.column === this._gridPos.entryField) {
            this._remove(child);
            this._addAt(new qxapp.component.form.FieldWHint(null, this._form.getControl(portId).description, this._form.getControl(portId)), i, {
              row: layoutProps.row,
              column: layoutProps.column
            });

            this.__retrievePortData(portId, i, layoutProps.row);
          }
        }
      }
    },

    __retrievePortData: function(portId, i, rowIdx) {
      const retrieving = new qx.ui.basic.Atom("", "qxapp/loading.gif");
      retrieving.key = portId;
      this._addAt(retrieving, i, {
        row: rowIdx,
        column: this._gridPos.retrieveStatus
      });

      this.fireDataEvent("dataFieldModified", portId);
    },

    retrievedPortData: function(portId) {
      let children = this._getChildren();
      for (let i=0; i<children.length; i++) {
        let child = children[i];
        if ("key" in child && child.key === portId) {
          const layoutProps = child.getLayoutProperties();
          if (layoutProps.column === this._gridPos.retrieveStatus) {
            this._remove(child);
          }
        }
      }
    },

    __arePortsCompatible: function(node1Id, port1Id, node2Id, port2Id) {
      if (this.getWorkbench() && node1Id && node2Id) {
        const node1 = this.getWorkbench().getNode(node1Id);
        const node2 = this.getWorkbench().getNode(node2Id);
        if (node1 && node2) {
          const port1 = node1.getOutput(port1Id);
          const port2 = node2.getInput(port2Id);
          return qxapp.data.Store.getInstance().arePortsCompatible(port1, port2);
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
