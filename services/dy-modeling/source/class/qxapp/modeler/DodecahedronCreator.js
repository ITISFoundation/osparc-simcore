qx.Class.define("qxapp.modeler.DodecahedronCreator", {
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
    _dodecahedron_material: null,
    _dodecahedron_temp: null,

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
        if (this._dodecahedron_temp) {
          this._threeView._threeWrapper.removeEntityFromScene(this._dodecahedron_temp);
        }
        let dodecahedronGeometry = this._threeView._threeWrapper.createDodecahedron(temp_radius);
        if (this._dodecahedron_material === null) {
          this._dodecahedron_material = this._threeView._threeWrapper.createNewMaterial();
        }
        this._dodecahedron_temp = this._threeView._threeWrapper.createEntity(dodecahedronGeometry, this._dodecahedron_material);

        this._updatePostion(this._dodecahedron_temp, this._centerPoint);

        this._threeView._threeWrapper.addEntityToScene(this._dodecahedron_temp);
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
          this._consolidateDodecahedron();
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

    _consolidateDodecahedron : function() {
      if (this._dodecahedron_temp) {
        this._threeView._threeWrapper.removeEntityFromScene(this._dodecahedron_temp);
        this._dodecahedron_temp = null;
      }

      let geometry = this._threeView._threeWrapper.createDodecahedron(this._radius);
      if (this._dodecahedron_material === null) {
        this._dodecahedron_material = this._threeView._threeWrapper.createNewMaterial();
      }
      let entity = this._threeView._threeWrapper.createEntity(geometry, this._dodecahedron_material);
      entity.name = "Dodecahedron";

      this._updatePostion(entity, this._centerPoint);

      this._threeView.addEntityToScene(entity);
      this._threeView.stopTool();
    }
  }
});
