/* global window */

qx.Class.define("qxapp.components.AvailableServices", {
  extend: qx.ui.container.Composite,

  include : [qx.locale.MTranslation],

  construct : function(width, height, backgroundColor, fontColor) {
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

    let bar = this.getAvailableServicesBar(width, backgroundColor);
    this.add(bar);
  },

  events : {
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
    _menubar: null,
    _moveBtn: null,
    _rotateBtn: null,
    _sphereBtn: null,
    _blockBtn: null,
    _cylinderBtn: null,
    _dodecaBtn: null,
    _splineBtn: null,

    getAvailableServicesBar : function(width, backgroundColor) {
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

      let disabled_btn = new qx.ui.toolbar.RadioButton(this.tr("Disabled"));
      disabled_btn.addListener("execute", function(e) {
        this.fireDataEvent("selectionModeChanged", 0);
      }, this);

      let sel_ent_btn = new qx.ui.toolbar.RadioButton(this.tr("Select entity"));
      sel_ent_btn.addListener("execute", function(e) {
        this.fireDataEvent("selectionModeChanged", 2);
      }, this);

      let sel_face_btn = new qx.ui.toolbar.RadioButton(this.tr("Select face"));
      sel_face_btn.addListener("execute", function(e) {
        this.fireDataEvent("selectionModeChanged", 3);
      }, this);

      selectionPart.add(disabled_btn);
      selectionPart.add(sel_ent_btn);
      selectionPart.add(sel_face_btn);

      let selectionGroup = new qx.ui.form.RadioGroup(disabled_btn, sel_ent_btn, sel_face_btn);
      selectionGroup.setAllowEmptySelection(true);

      // Move
      let transformPart = new qx.ui.toolbar.Part();
      toolbar.add(transformPart);

      this._moveBtn = new qx.ui.toolbar.CheckBox(this.tr("Move"));
      this._moveBtn.addListener("execute", this._onMoveToolRequested.bind(this));

      this._rotateBtn = new qx.ui.toolbar.CheckBox(this.tr("Rotate"));
      this._rotateBtn.addListener("execute", this._onRotateToolRequested.bind(this));

      transformPart.add(this._moveBtn);
      transformPart.add(this._rotateBtn);

      let transformGroup = new qx.ui.form.RadioGroup(this._moveBtn, this._rotateBtn);
      transformGroup.setAllowEmptySelection(true);
      transformGroup.setSelection([]);

      // Create standard model
      let drawingPart = new qx.ui.toolbar.Part();
      toolbar.add(drawingPart);

      this._sphereBtn = new qx.ui.toolbar.RadioButton(this.tr("Add Sphere"));
      this._sphereBtn.addListener("execute", this._onAddSphereRequested, this);

      this._blockBtn = new qx.ui.toolbar.RadioButton(this.tr("Add Box"));
      this._blockBtn.addListener("execute", this._onAddBlockRequested.bind(this));

      this._cylinderBtn = new qx.ui.toolbar.RadioButton(this.tr("Add Cylinder"));
      this._cylinderBtn.addListener("execute", this._onAddCylinderRequested.bind(this));

      this._dodecaBtn = new qx.ui.toolbar.RadioButton(this.tr("Add Dodecahedron"));
      this._dodecaBtn.addListener("execute", this._onAddDodecaRequested.bind(this));

      this._splineBtn = new qx.ui.toolbar.RadioButton(this.tr("Add Spline"));
      this._splineBtn.addListener("execute", this._onAddSplineRequested.bind(this));

      drawingPart.add(this._sphereBtn);
      drawingPart.add(this._blockBtn);
      drawingPart.add(this._cylinderBtn);
      drawingPart.add(this._dodecaBtn);
      drawingPart.add(this._splineBtn);

      let drawingGroup = new qx.ui.form.RadioGroup(this._sphereBtn, this._blockBtn, this._cylinderBtn, this._dodecaBtn, this._splineBtn);
      drawingGroup.setAllowEmptySelection(true);
      drawingGroup.setSelection([]);

      // Boolean operations
      let menuPart = new qx.ui.toolbar.Part();
      toolbar.add(menuPart);

      let booleanMenu = new qx.ui.toolbar.MenuButton("Boolean operations");
      booleanMenu.setMenu(this._getBooleanMenu());
      menuPart.add(booleanMenu);

      return frame;
    },

    _getBooleanMenu : function() {
      let menu = new qx.ui.menu.Menu();

      let uniteButton = new qx.ui.menu.Button(this.tr("Unite"));
      let intersectButton = new qx.ui.menu.Button(this.tr("Intersect"));
      let substractButton = new qx.ui.menu.Button(this.tr("Substract"));

      uniteButton.addListener("execute", this._onBooleanUniteRequested.bind(this));
      intersectButton.addListener("execute", this._onBooleanIntersectRequested.bind(this));
      substractButton.addListener("execute", this._onBooleanSubstractRequested.bind(this));

      menu.add(uniteButton);
      menu.add(intersectButton);
      menu.add(substractButton);

      return menu;
    },

    _onAddSphereRequested : function() {
      this.fireDataEvent("newSphereRequested", this._sphereBtn.getValue());
    },

    _onAddBlockRequested : function() {
      this.fireDataEvent("newBlockRequested", this._blockBtn.getValue());
    },

    _onAddCylinderRequested : function() {
      this.fireDataEvent("newCylinderRequested", this._cylinderBtn.getValue());
    },

    _onAddDodecaRequested : function() {
      this.fireDataEvent("newDodecaRequested", this._dodecaBtn.getValue());
    },

    _onAddSplineRequested : function() {
      this.fireDataEvent("newSplineRequested", this._splineBtn.getValue());
    },

    _onMoveToolRequested : function() {
      this.fireDataEvent("moveToolRequested", this._moveBtn.getValue());
    },

    _onRotateToolRequested : function() {
      this.fireDataEvent("rotateToolRequested", this._rotateBtn.getValue());
    },

    _onBooleanUniteRequested : function() {
      this.fireDataEvent("booleanOperationRequested", 0);
    },

    _onBooleanIntersectRequested : function() {
      this.fireDataEvent("booleanOperationRequested", 1);
    },

    _onBooleanSubstractRequested : function() {
      this.fireDataEvent("booleanOperationRequested", 2);
    }
  }
});
