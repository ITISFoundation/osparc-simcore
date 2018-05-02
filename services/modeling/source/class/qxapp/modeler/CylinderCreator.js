qx.Class.define("qxapp.modeler.CylinderCreator", {
  extend: qx.core.Object,

  construct : function(threeViewer) {
    this._threeView = threeViewer;

    this._steps = {
      center: 0,
      radius: 1,
      height: 2
    };
  },

  members : {
    _threeView: null,
    _steps: null,
    _nextStep: 0,
    _centerPos: null,
    _radius: null,
    _height: null,
    _plane_material: null,
    _circle_temp: null,
    _cylinder_material: null,
    _cylinder_temp: null,

    startTool : function() {
      const fixed_axe = 2;
      const fixed_pos = 0;
      this._threeView.addInvisiblePlane(fixed_axe, fixed_pos);
    },

    stopTool : function() {
      this._threeView.removeInvisiblePlane();
    },

    _removeTemps : function() {
      if (this._circle_temp) {
        this._threeView._threeWrapper.removeEntityFromScene(this._circle_temp);
      }
      if (this._cylinder_temp) {
        this._threeView._threeWrapper.removeEntityFromScene(this._cylinder_temp);
      }
    },

    onMouseHover : function(event, intersects) {
      if (intersects.length > 0) {
        let intersect = intersects[0];
        if (this._nextStep === this._steps.radius) {
          this._removeTemps();

          let temp_radius = Math.hypot(intersect.point.x-this._centerPos.x, intersect.point.y-this._centerPos.y);
          let circleGeometry = this._threeView._threeWrapper.createCylinder(temp_radius);
          if (this._plane_material === null) {
            this._plane_material = this._threeView._threeWrapper.createNewPlaneMaterial();
          }
          this._circle_temp = this._threeView._threeWrapper.createEntity(circleGeometry, this._plane_material);

          this._updatePosition(this._circle_temp, this._centerPos);

          this._threeView._threeWrapper.addEntityToScene(this._circle_temp);
        } else if (this._nextStep === this._steps.height) {
          this._removeTemps();

          let temp_height = intersect.point.z - this._centerPos.z;
          let cylinderGeometry = this._threeView._threeWrapper.createCylinder(this._radius, temp_height);
          if (this._cylinder_material === null) {
            this._cylinder_material = this._threeView._threeWrapper.createNewMaterial(this._plane_material.color.r, this._plane_material.color.g, this._plane_material.color.b);
          }
          this._cylinder_temp = this._threeView._threeWrapper.createEntity(cylinderGeometry, this._cylinder_material);

          this._updatePosition(this._cylinder_temp, this._centerPos, temp_height);

          this._threeView._threeWrapper.addEntityToScene(this._cylinder_temp);
        }
      }
      return true;
    },

    onMouseDown : function(event, intersects) {
      if (intersects.length > 0) {
        let intersect = intersects[0];

        if (this._centerPos === null) {
          this._centerPos = intersect.point;
          this._nextStep = this._steps.radius;
        } else if (this._radius === null) {
          this._radius = Math.hypot(intersect.point.x-this._centerPos.x, intersect.point.y-this._centerPos.y);
          this._nextStep = this._steps.height;
          this._threeView.removeInvisiblePlane();
          this._threeView.addInvisiblePlane(0, this._centerPos.x);
        } else if (this._height === null) {
          this._height = intersect.point.z - this._centerPos.z;
          this._consolidateCylinder();
          this._nextStep = 3;
        }
      }

      return true;
    },

    _updatePosition(mesh, center, height) {
      if (height === undefined) {
        mesh.position.x = center.x;
        mesh.position.y = center.y;
        mesh.position.z = center.z;
      } else {
        mesh.rotation.x = Math.PI / 2;
        mesh.position.x = center.x;
        mesh.position.y = center.y;
        mesh.position.z = height/2;
      }
    },

    _consolidateCylinder : function() {
      this._removeTemps();
      if (this._circle_temp) {
        this._circle_temp = null;
      }
      if (this._cylinder_temp) {
        this._cylinder_temp = null;
      }

      let geometry = this._threeView._threeWrapper.createCylinder(this._radius, this._height);
      if (this._cylinder_material === null) {
        this._cylinder_material = this._threeView._threeWrapper.createNewMaterial();
      }
      let entity = this._threeView._threeWrapper.createEntity(geometry, this._cylinder_material);
      entity.name = "Cylinder";

      this._updatePosition(entity, this._centerPos, this._height);

      this._threeView.addEntityToScene(entity);
      this._threeView.stopTool();
    }
  }
});
