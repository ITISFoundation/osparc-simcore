qx.Class.define("qxapp.modeler.BoxCreator", {
  extend: qx.core.Object,

  construct : function(threeViewer) {
    this._threeView = threeViewer;

    this._steps = {
      corner0: 0,
      corner1: 1,
      corner2: 2
    };
  },

  members: {
    _threeView: null,
    _steps: null,
    _nextStep: 0,
    _corner0Pos: null,
    _corner1Pos: null,
    _corner2Pos: null,
    _plane_material: null,
    _square_temp: null,
    _box_material: null,
    _box_temp: null,

    startTool : function() {
      const fixed_axe = 2;
      const fixed_pos = 0;
      this._threeView.addInvisiblePlane(fixed_axe, fixed_pos);
    },

    stopTool : function() {
      this._threeView.removeInvisiblePlane();
    },

    _removeTemps : function() {
      if (this._square_temp) {
        this._threeView._threeWrapper.removeEntityFromScene(this._square_temp);
      }
      if (this._box_temp) {
        this._threeView._threeWrapper.removeEntityFromScene(this._box_temp);
      }
    },

    onMouseHover : function(event, intersects) {
      if (intersects.length > 0) {
        let intersect = intersects[0];
        if (this._nextStep === this._steps.corner1) {
          this._removeTemps();

          let squareGeometry = this._threeView._threeWrapper.createBox(this._corner0Pos, intersect.point);
          if (this._plane_material === null) {
            this._plane_material = this._threeView._threeWrapper.createNewPlaneMaterial();
          }
          this._square_temp = this._threeView._threeWrapper.createEntity(squareGeometry, this._plane_material);

          this._updatePosition(this._square_temp, this._corner0Pos, intersect.point);

          this._threeView._threeWrapper.addEntityToScene(this._square_temp);
        } else if (this._nextStep === this._steps.corner2) {
          this._removeTemps();

          let boxGeometry = this._threeView._threeWrapper.createBox(this._corner0Pos, this._corner1Pos, intersect.point);
          if (this._box_material === null) {
            this._box_material = this._threeView._threeWrapper.createNewMaterial(this._plane_material.color.r, this._plane_material.color.g, this._plane_material.color.b);
          }
          this._box_temp = this._threeView._threeWrapper.createEntity(boxGeometry, this._box_material);

          this._updatePosition(this._box_temp, this._corner0Pos, this._corner1Pos, intersect.point);

          this._threeView._threeWrapper.addEntityToScene(this._box_temp);
        }
      }
      return true;
    },

    onMouseDown : function(event, intersects) {
      if (intersects.length > 0) {
        let intersect = intersects[0];

        if (this._corner0Pos === null) {
          this._corner0Pos = intersect.point;
          this._nextStep = this._steps.corner1;
        } else if (this._corner1Pos === null) {
          this._corner1Pos = intersect.point;
          this._nextStep = this._steps.corner2;
          this._threeView.removeInvisiblePlane();
          this._threeView.addInvisiblePlane(0, this._corner1Pos.x);
        } else if (this._corner2Pos === null) {
          this._corner2Pos = intersect.point;
          this._consolidateBox();
          this._nextStep = 3;
        }
      }

      return true;
    },

    _updatePosition(mesh, p1, p2, p3) {
      let width = Math.abs(p2.x - p1.x);
      let height = Math.abs(p2.y - p1.y);
      let depth = 0;
      let originX = Math.min(p1.x, p2.x);
      let originY = Math.min(p1.y, p2.y);
      let originZ = 0;
      if (p3 === undefined) {
        depth = Math.abs(p1.z - p2.z);
        originZ = Math.min(p1.z, p2.z);
      } else {
        depth = Math.abs(p3.z - p2.z);
        originZ = Math.min(p1.z, p3.z);
      }
      mesh.position.x = originX + width/2;
      mesh.position.y = originY + height/2;
      mesh.position.z = originZ + depth/2;
    },

    _consolidateBox : function() {
      this._removeTemps();
      if (this._square_temp) {
        this._square_temp = null;
      }
      if (this._box_temp) {
        this._box_temp = null;
      }

      let geometry = this._threeView._threeWrapper.createBox(this._corner0Pos, this._corner1Pos, this._corner2Pos);
      if (this._box_material === null) {
        this._box_material = this._threeView._threeWrapper.createNewMaterial();
      }
      let entity = this._threeView._threeWrapper.createEntity(geometry, this._box_material);
      entity.name = "Box";

      this._updatePosition(entity, this._corner0Pos, this._corner1Pos, this._corner2Pos);

      this._threeView.addEntityToScene(entity);
      this._threeView.stopTool();
    }
  }
});
