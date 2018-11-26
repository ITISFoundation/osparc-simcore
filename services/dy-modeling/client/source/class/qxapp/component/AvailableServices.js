/* global window */

qx.Class.define("qxapp.component.AvailableServices", {
  extend: qx.ui.container.Composite,

  include: [qx.locale.MTranslation],

  construct: function(width, height, backgroundColor, fontColor) {
    this.base(arguments);

    let box = new qx.ui.layout.HBox();
    box.set({
      // alignX: "center",
      // alignY: "middle",
      spacing: 10
    });

    this.set({
      layout: box,
      width: width,
      height: height
    });

    let bar = this.__getAvailableServicesBar(width, backgroundColor);
    this.add(bar);
  },

  events: {
    "selectionModeChanged": "qx.event.type.Data",
    "moveToolRequested": "qx.event.type.Data",
    "rotateToolRequested": "qx.event.type.Data",
    "newSphereRequested": "qx.event.type.Data",
    "newBlockRequested": "qx.event.type.Data",
    "newCylinderRequested": "qx.event.type.Data",
    "newDodecaRequested": "qx.event.type.Data",
    "newSplineRequested": "qx.event.type.Data",
    "booleanOperationRequested": "qx.event.type.Data"
  },

  members: {
    __menubar: null,
    __moveBtn: null,
    __rotateBtn: null,
    __sphereBtn: null,
    __blockBtn: null,
    __cylinderBtn: null,
    __dodecaBtn: null,
    __splineBtn: null,

    getMoveBtn: function() {
      return this.__moveBtn;
    },

    getRotateBtn: function() {
      return this.__rotateBtn;
    },

    __getAvailableServicesBar: function(width, backgroundColor) {
      let frame = new qx.ui.container.Composite(new qx.ui.layout.Grow());

      let toolbar = new qx.ui.toolbar.ToolBar();
      toolbar.set({
        width: width,
        backgroundColor: backgroundColor
      });

      window.addEventListener("resize", function() {
        toolbar.set({
          width: window.innerWidth
        });
      });

      frame.add(toolbar);

      // Model selection
      let selectionPart = new qx.ui.toolbar.Part();
      toolbar.add(selectionPart);

      let disabledBtn = new qx.ui.toolbar.RadioButton(this.tr("Disabled"));
      disabledBtn.addListener("execute", function(e) {
        this.fireDataEvent("selectionModeChanged", 0);
      }, this);

      let selEntBtn = new qx.ui.toolbar.RadioButton(this.tr("Select entity"));
      selEntBtn.addListener("execute", function(e) {
        this.fireDataEvent("selectionModeChanged", 2);
      }, this);

      let selFaceBtn = new qx.ui.toolbar.RadioButton(this.tr("Select face"));
      selFaceBtn.addListener("execute", function(e) {
        this.fireDataEvent("selectionModeChanged", 3);
      }, this);

      selectionPart.add(disabledBtn);
      selectionPart.add(selEntBtn);
      // selectionPart.add(selFaceBtn);

      if (qx.core.Environment.get("qxapp.isModeler")) {
        let selectionGroup = new qx.ui.form.RadioGroup(disabledBtn, selEntBtn, selFaceBtn);
        selectionGroup.setAllowEmptySelection(true);

        // Move
        let transformPart = new qx.ui.toolbar.Part();
        toolbar.add(transformPart);

        this.__moveBtn = new qx.ui.toolbar.CheckBox(this.tr("Move"));
        this.__moveBtn.addListener("execute", this.__onMoveToolRequested.bind(this));

        this.__rotateBtn = new qx.ui.toolbar.CheckBox(this.tr("Rotate"));
        this.__rotateBtn.addListener("execute", this.__onRotateToolRequested.bind(this));

        transformPart.add(this.__moveBtn);
        transformPart.add(this.__rotateBtn);

        let transformGroup = new qx.ui.form.RadioGroup(this.__moveBtn, this.__rotateBtn);
        transformGroup.setAllowEmptySelection(true);
        transformGroup.setSelection([]);

        // Create standard model
        let drawingPart = new qx.ui.toolbar.Part();
        toolbar.add(drawingPart);

        this.__sphereBtn = new qx.ui.toolbar.RadioButton(this.tr("Add Sphere"));
        this.__sphereBtn.addListener("execute", this.__onAddSphereRequested, this);

        this.__blockBtn = new qx.ui.toolbar.RadioButton(this.tr("Add Box"));
        this.__blockBtn.addListener("execute", this.__onAddBlockRequested.bind(this));

        this.__cylinderBtn = new qx.ui.toolbar.RadioButton(this.tr("Add Cylinder"));
        this.__cylinderBtn.addListener("execute", this._onAddCylinderRequested.bind(this));

        this.__dodecaBtn = new qx.ui.toolbar.RadioButton(this.tr("Add Dodecahedron"));
        this.__dodecaBtn.addListener("execute", this.__onAddDodecaRequested.bind(this));

        this.__splineBtn = new qx.ui.toolbar.RadioButton(this.tr("Add Spline"));
        this.__splineBtn.addListener("execute", this.__onAddSplineRequested.bind(this));

        drawingPart.add(this.__sphereBtn);
        drawingPart.add(this.__blockBtn);
        drawingPart.add(this.__cylinderBtn);
        drawingPart.add(this.__dodecaBtn);
        drawingPart.add(this.__splineBtn);

        let drawingGroup = new qx.ui.form.RadioGroup(this.__sphereBtn, this.__blockBtn, this.__cylinderBtn, this.__dodecaBtn, this.__splineBtn);
        drawingGroup.setAllowEmptySelection(true);
        drawingGroup.setSelection([]);

        // Boolean operations
        let menuPart = new qx.ui.toolbar.Part();
        toolbar.add(menuPart);

        let booleanMenu = new qx.ui.toolbar.MenuButton("Boolean operations");
        booleanMenu.setMenu(this.__getBooleanMenu());
        menuPart.add(booleanMenu);
      }

      return frame;
    },

    __getBooleanMenu: function() {
      let menu = new qx.ui.menu.Menu();

      let uniteButton = new qx.ui.menu.Button(this.tr("Unite"));
      let intersectButton = new qx.ui.menu.Button(this.tr("Intersect"));
      let substractButton = new qx.ui.menu.Button(this.tr("Substract"));

      uniteButton.addListener("execute", this.__onBooleanUniteRequested.bind(this));
      intersectButton.addListener("execute", this.__onBooleanIntersectRequested.bind(this));
      substractButton.addListener("execute", this.__onBooleanSubstractRequested.bind(this));

      menu.add(uniteButton);
      menu.add(intersectButton);
      menu.add(substractButton);

      return menu;
    },

    __onAddSphereRequested: function() {
      this.fireDataEvent("newSphereRequested", this.__sphereBtn.getValue());
    },

    __onAddBlockRequested: function() {
      this.fireDataEvent("newBlockRequested", this.__blockBtn.getValue());
    },

    _onAddCylinderRequested: function() {
      this.fireDataEvent("newCylinderRequested", this.__cylinderBtn.getValue());
    },

    __onAddDodecaRequested: function() {
      this.fireDataEvent("newDodecaRequested", this.__dodecaBtn.getValue());
    },

    __onAddSplineRequested: function() {
      this.fireDataEvent("newSplineRequested", this.__splineBtn.getValue());
    },

    __onMoveToolRequested: function() {
      this.fireDataEvent("moveToolRequested", this.__moveBtn.getValue());
    },

    __onRotateToolRequested: function() {
      this.fireDataEvent("rotateToolRequested", this.__rotateBtn.getValue());
    },

    __onBooleanUniteRequested: function() {
      this.fireDataEvent("booleanOperationRequested", 0);
    },

    __onBooleanIntersectRequested: function() {
      this.fireDataEvent("booleanOperationRequested", 1);
    },

    __onBooleanSubstractRequested: function() {
      this.fireDataEvent("booleanOperationRequested", 2);
    }
  }
});
