/* global window */

qx.Class.define("qxapp.modeler.SphereCreatorS4L", {
  extend: qx.core.Object,

  construct : function(threeViewer) {
    this._threeView = threeViewer;
    this._my_uuid = this.uuidv4();
    console.log("new id", this._my_uuid);

    this._steps = {
      centerPoint: 0,
      radius: 1
    };
  },

  events : {
    "newSphereS4LRequested": "qx.event.type.Data"
  },

  members : {
    _threeView: null,
    _steps: null,
    _nextStep: 0,
    _centerPoint: null,
    _radius: null,
    _sphere_material: null,
    _sphere_temp: null,
    _uuid_temp: "",
    _my_uuid: "",

    uuidv4 : function() {
      return ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c =>
        (c ^ window.crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16));
    },

    startTool : function() {
      const fixed_axe = 2;
      const fixed_pos = 0;
      this._threeView.addInvisiblePlane(fixed_axe, fixed_pos);
    },

    stopTool : function() {
      this._threeView.removeInvisiblePlane();
    },

    onMouseHover : function(event, intersects) {
      if (this._uuid_temp === "") {
        return;
      }

      if (intersects.length > 0 && this._nextStep === this._steps.radius) {
        let intersect = intersects[0];
        let temp_radius = Math.hypot(intersect.point.x-this._centerPoint.x, intersect.point.y-this._centerPoint.y);
        this.fireDataEvent("newSphereS4LRequested", [temp_radius, this._centerPoint, this._uuid_temp]);
      }
    },

    onMouseDown : function(event, intersects) {
      if (intersects.length > 0) {
        let intersect = intersects[0];

        if (this._centerPoint === null) {
          this._centerPoint = intersect.point;
          this._nextStep = this._steps.radius;
          let dummyRadius = 0.0001;
          this._uuid_temp = this.uuidv4();
          this.fireDataEvent("newSphereS4LRequested", [dummyRadius, this._centerPoint, this._uuid_temp]);
          return true;
        }

        if (this._radius === null) {
          this._radius = Math.hypot(intersect.point.x-this._centerPoint.x, intersect.point.y-this._centerPoint.y);
          this.fireDataEvent("newSphereS4LRequested", [this._radius, this._centerPoint, this._my_uuid]);
          return true;
        }
      }

      return true;
    },

    sphereFromS4L : function(response) {
      let sphereGeometry = this._threeView._threeWrapper.fromEntityMeshToEntity(response.value[0]);
      // let sphereMaterial = this._threeView._threeWrapper.CreateMeshNormalMaterial();
      let color = response.value[0].material.diffuse;
      let sphereMaterial = this._threeView._threeWrapper.createNewMaterial(color.r, color.g, color.b);
      let sphere = this._threeView._threeWrapper.createEntity(sphereGeometry, sphereMaterial);

      this._threeView._threeWrapper.applyTransformationMatrixToEntity(sphere, response.value[0].transform4x4);

      sphere.name = "Sphere_S4L";
      sphere.uuid = response.uuid;

      if (this._sphere_temp) {
        this._threeView._threeWrapper.removeEntityFromScene(this._sphere_temp);
      }

      if (this._my_uuid === sphere.uuid) {
        this._consolidateSphere(sphere);
      } else {
        this._sphere_temp = sphere;
        this._threeView._threeWrapper.addEntityToScene(this._sphere_temp);
      }
    },

    _consolidateSphere : function(sphere) {
      sphere.name = "Sphere_S4L";
      this._threeView.addEntityToScene(sphere);
      this._uuid_temp = "";
      this._threeView.stopTool();
    }
  }
});
