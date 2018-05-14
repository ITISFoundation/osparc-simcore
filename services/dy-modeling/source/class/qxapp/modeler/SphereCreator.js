qx.Class.define("qxapp.modeler.SphereCreator", {
  extend: qx.core.Object,

  construct : function(threeViewer) {
    this._threeView = threeViewer;

    this._steps = {
      centerPoint: 0,
      radius: 1
    };
  },

  members : {
    _threeView: null,
    _steps: null,
    _nextStep: 0,
    _centerPoint: null,
    _radius: null,
    _sphere_material: null,
    _sphere_temp: null,

    startTool : function() {
      const fixed_axe = 2;
      const fixed_pos = 0;
      this._threeView.addInvisiblePlane(fixed_axe, fixed_pos);
    },

    stopTool : function() {
      this._threeView.removeInvisiblePlane();
    },

    onMouseHover : function(event, intersects) {
      if (intersects.length > 0 && this._nextStep === this._steps.radius) {
        let intersect = intersects[0];
        let temp_radius = Math.hypot(intersect.point.x-this._centerPoint.x, intersect.point.y-this._centerPoint.y);
        if (this._sphere_temp) {
          this._threeView._threeWrapper.removeEntityFromScene(this._sphere_temp);
        }
        let sphereGeometry = this._threeView._threeWrapper.createSphere(temp_radius);
        if (this._sphere_material === null) {
          this._sphere_material = this._threeView._threeWrapper.createNewMaterial();
        }
        this._sphere_temp = this._threeView._threeWrapper.createEntity(sphereGeometry, this._sphere_material);

        this._updatePostion(this._sphere_temp, this._centerPoint);

        this._threeView._threeWrapper.addEntityToScene(this._sphere_temp);
      }

      return true;
    },

    onMouseDown : function(event, intersects) {
      if (intersects.length > 0) {
        let intersect = intersects[0];

        if (this._centerPoint === null) {
          this._centerPoint = intersect.point;
          this._nextStep = this._steps.radius;
          return true;
        }

        if (this._radius === null) {
          this._radius = Math.hypot(intersect.point.x-this._centerPoint.x, intersect.point.y-this._centerPoint.y);
          this._consolidateSphere();
          return true;
        }
      }

      return true;
    },

    _updatePostion : function(mesh, center) {
      mesh.position.x = center.x;
      mesh.position.y = center.y;
      mesh.position.z = center.z;
    },

    _consolidateSphere : function() {
      if (this._sphere_temp) {
        this._threeView._threeWrapper.removeEntityFromScene(this._sphere_temp);
        this._sphere_temp = null;
      }

      let geometry = this._threeView._threeWrapper.createSphere(this._radius);
      if (this._sphere_material === null) {
        this._sphere_material = this._threeView._threeWrapper.createNewMaterial();
      }
      let entity = this._threeView._threeWrapper.createEntity(geometry, this._sphere_material);
      entity.name = "Sphere";

      this._updatePostion(entity, this._centerPoint);

      this._threeView.addEntityToScene(entity);
      this._threeView.stopTool();
    }
  }
});
