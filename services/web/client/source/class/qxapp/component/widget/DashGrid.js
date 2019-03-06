qx.Class.define("qxapp.component.widget.DashGrid", {
  extend: qx.ui.core.Widget,

  construct: function(containerNode) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());

    this.setContainerNode(containerNode);

    this.__cellEditors = {};
    this.__outputs = {};
    let stack = this.__stack = new qx.ui.container.Stack();
    let mainView = this.__mainView = new qx.ui.container.Composite(new qx.ui.layout.VBox());
    stack.add(mainView);

    let addBtn = new qx.ui.form.Button(this.tr("Add plot"));
    addBtn.addListener("execute", e => {
      this.addClonedNode();
    }, this);
    mainView.add(addBtn);

    let dashboradLayout = new qx.ui.container.Composite(new qx.ui.layout.Canvas());
    let gridster = this.__gridterWr = new qxapp.wrapper.Gridster();
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
    mainView.add(dashboradLayout, {
      flex: 1
    });

    this._add(stack, {
      top: 0,
      right: 0,
      bottom: 0,
      left: 0
    });

    const innerNodes = containerNode.getInnerNodes();
    for (const uuid in innerNodes) {
      this.addNode(innerNodes[uuid]);
    }
  },

  events: {
    "widgetSelected": "qx.event.type.Data"
  },

  properties: {
    containerNode: {
      check: "qxapp.data.model.Node",
      nullable: true
    }
  },

  members: {
    __stack: null,
    __mainView: null,
    __cellEditors: null,
    __gridterWr: null,

    addNode: function(node) {
      let parentNode = this.getContainerNode();
      if (parentNode) {
        let workbench = parentNode.getWorkbench();
        workbench.addNode(node, parentNode);

        this.addWidget(node);
      }
    },

    addClonedNode: function() {
      let parentNode = this.getContainerNode();
      if (parentNode) {
        let workbench = parentNode.getWorkbench();
        const baseNode = parentNode.getInnerNodes()["inner1_raw"];
        let newNode = workbench.cloneNode(baseNode);
        this.addNode(newNode);
      }
    },

    addWidget: function(node) {
      let cellHandler = new qxapp.component.widget.cell.Handler(node);

      let cellEditor = new qxapp.component.widget.cell.Editor(cellHandler);
      cellEditor.addListener("backToGrid", () => {
        this.__stack.setSelection([this.__mainView]);
      }, this);
      this.__cellEditors[cellHandler.getUuid()] = cellEditor;

      let cellOutput = new qxapp.component.widget.cell.Output(cellHandler);
      let htmlElement = this.__gridterWr.addWidget(cellOutput);
      if (htmlElement) {
        // this.__outputs[cellHandler.getUuid()] = htmlElement;
        cellHandler.addListener("changeTitle", e => {
          this.__gridterWr.rebuildWidget(cellOutput, htmlElement);
        }, this);
      }
    }
  }
});
