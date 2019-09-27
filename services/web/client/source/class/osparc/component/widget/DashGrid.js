qx.Class.define("osparc.component.widget.DashGrid", {
  extend: qx.ui.core.Widget,

  construct: function(containerNode) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());

    this.setContainerNode(containerNode);

    this.__cellEditors = {};
    this.__outputs = {};
    let stack = this.__stack = new qx.ui.container.Stack();
    let gridView = this.__gridView = new qx.ui.container.Composite(new qx.ui.layout.VBox());
    stack.add(gridView);

    let controls = new qx.ui.container.Composite(new qx.ui.layout.HBox());
    controls.add(new qx.ui.core.Spacer(), {
      flex: 1
    });
    let addBtn = new qx.ui.form.Button(this.tr("Add plot")).set({
      height: 25,
      width: 300
    });
    addBtn.addListener("execute", e => {
      this.addClonedNode();
    }, this);
    controls.add(addBtn);
    controls.add(new qx.ui.core.Spacer(), {
      flex: 1
    });
    gridView.add(controls);


    let dashboradLayout = new qx.ui.container.Composite(new qx.ui.layout.Canvas());
    let gridster = this.__gridterWr = new osparc.wrapper.Gridster();
    gridster.addListener(("gridsterLibReady"), e => {
      let ready = e.getData();
      if (ready) {
        const values = Object.values(containerNode.getInnerNodes());
        for (const value of values) {
          this.addNode(value);
        }
      }
    }, this);
    gridster.addListener("widgetSelected", e => {
      const uuid = e.getData();
      if (Object.prototype.hasOwnProperty.call(this.__cellEditors, uuid)) {
        let cellEditor = this.__cellEditors[uuid];
        this.__stack.add(cellEditor);
        this.__stack.setSelection([cellEditor]);
      }
    }, this);
    dashboradLayout.add(gridster, {
      top: 0,
      right: 0,
      bottom: 0,
      left: 0
    });
    gridView.add(dashboradLayout, {
      flex: 1
    });

    this._add(stack, {
      top: 0,
      right: 0,
      bottom: 0,
      left: 0
    });
  },

  events: {
    "widgetSelected": "qx.event.type.Data"
  },

  properties: {
    containerNode: {
      check: "osparc.data.model.Node",
      nullable: true
    }
  },

  members: {
    __stack: null,
    __gridView: null,
    __cellEditors: null,
    __gridterWr: null,

    addNode: function(node) {
      let parentNode = this.getContainerNode();
      if (parentNode) {
        let workbench = parentNode.getWorkbench();
        workbench.addNode(node, parentNode);
        const success = this.addWidget(node);
        if (!success) {
          workbench.removeNode(node.getNodeId());
        }
      }
    },

    addClonedNode: function() {
      let parentNode = this.getContainerNode();
      if (parentNode) {
        let workbench = parentNode.getWorkbench();
        const innerNodes = Object.values(parentNode.getInnerNodes());
        if (innerNodes.length > 0) {
          const node = workbench.cloneNode(innerNodes[0]);
          const success = this.addWidget(node);
          if (!success) {
            workbench.removeNode(node.getNodeId());
          }
        }
      }
    },

    addWidget: function(node) {
      let cellHandler = new osparc.component.widget.cell.Handler(node);

      let cellEditor = new osparc.component.widget.cell.Editor(cellHandler);
      cellEditor.addListener("backToGrid", () => {
        cellHandler.retrieveOutput();
        this.__stack.setSelection([this.__gridView]);
      }, this);
      this.__cellEditors[cellHandler.getUuid()] = cellEditor;

      let cellOutput = new osparc.component.widget.cell.Output(cellHandler);

      let htmlElement = this.__gridterWr.addWidget(cellOutput);
      if (htmlElement) {
        // this.__outputs[cellHandler.getUuid()] = htmlElement;
        node.addListener("changeLabel", e => {
          this.__gridterWr.rebuildWidget(cellOutput, htmlElement);
        }, this);
        cellHandler.addListener("outputUpdated", () => {
          this.__gridterWr.rebuildWidget(cellOutput, htmlElement);
          const parentNode = this.getContainerNode();
          const plot = htmlElement.getElementsByTagName("svg")[0];
          if (parentNode && plot) {
            plot.style.WebkitTouchCallout = "none";
            plot.style.WebkitUserSelect = "none";
            plot.style.userSelect = "none";
          }
        }, this);
        cellHandler.retrieveOutput();
        return true;
      }
      return false;
    }
  }
});
