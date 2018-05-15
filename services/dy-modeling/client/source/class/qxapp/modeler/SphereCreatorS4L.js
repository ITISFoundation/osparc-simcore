/* global window */

qx.Class.define("qxapp.modeler.SphereCreatorS4L", {
  extend: qx.core.Object,

  construct : function(threeViewer) {
    this.__threeView = threeViewer;
    this.__myUuid = this.uuidv4();
    console.log("new id", this.__myUuid);

    this.__steps = {
      centerPoint: 0,
      radius: 1
    };
  },

  events : {
    "newSphereS4LRequested": "qx.event.type.Data"
  },

  members : {
    __threeView: null,
    __steps: null,
    __nextStep: 0,
    __centerPoint: null,
    __radius: null,
    __sphereMaterial: null,
    __sphereTemp: null,
    __uuidTemp: "",
    __myUuid: "",

    uuidv4: function() {
      return ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c =>
        (c ^ window.crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16));
    },

    startTool: function() {
      const fixedAxe = 2;
      const fixedPos = 0;
      this.__threeView.addInvisiblePlane(fixedAxe, fixedPos);
    },

    stopTool: function() {
      this.__threeView.removeInvisiblePlane();
    },

    onMouseHover: function(event, intersects) {
      if (this.__uuidTemp === "") {
        return;
      }

      if (intersects.length > 0 && this.__nextStep === this.__steps.radius) {
        let intersect = intersects[0];
        let tempRadius = Math.hypot(intersect.point.x-this.__centerPoint.x, intersect.point.y-this.__centerPoint.y);
        this.fireDataEvent("newSphereS4LRequested", [tempRadius, this.__centerPoint, this.__uuidTemp]);
      }
    },

    onMouseDown: function(event, intersects) {
      if (intersects.length > 0) {
        let intersect = intersects[0];

        if (this.__centerPoint === null) {
          this.__centerPoint = intersect.point;
          this.__nextStep = this.__steps.radius;
          let dummyRadius = 0.0001;
          this.__uuidTemp = this.uuidv4();
          this.fireDataEvent("newSphereS4LRequested", [dummyRadius, this.__centerPoint, this.__uuidTemp]);
          return true;
        }

        if (this.__radius === null) {
          this.__radius = Math.hypot(intersect.point.x-this.__centerPoint.x, intersect.point.y-this.__centerPoint.y);
          this.fireDataEvent("newSphereS4LRequested", [this.__radius, this.__centerPoint, this.__myUuid]);
          return true;
        }
      }

      return true;
    },

    sphereFromS4L: function(response) {
      let sphereGeometry = this.__threeView.getThreeWrapper().fromEntityMeshToEntity(response.value[0]);
      // let sphereMaterial = this.__threeView.getThreeWrapper().CreateMeshNormalMaterial();
      let color = response.value[0].material.diffuse;
      let sphereMaterial = this.__threeView.getThreeWrapper().createNewMaterial(color.r, color.g, color.b);
      let sphere = this.__threeView.getThreeWrapper().createEntity(sphereGeometry, sphereMaterial);

      this.__threeView.getThreeWrapper().applyTransformationMatrixToEntity(sphere, response.value[0].transform4x4);

      sphere.name = "Sphere_S4L";
      sphere.uuid = response.uuid;

      if (this.__sphereTemp) {
        this.__threeView.getThreeWrapper().removeEntityFromScene(this.__sphereTemp);
      }

      if (this.__myUuid === sphere.uuid) {
        this.__consolidateSphere(sphere);
      } else {
        this.__sphereTemp = sphere;
        this.__threeView.getThreeWrapper().addEntityToScene(this.__sphereTemp);
      }
    },

    __consolidateSphere: function(sphere) {
      sphere.name = "Sphere_S4L";
      this.__threeView.addEntityToScene(sphere);
      this.__uuidTemp = "";
      this.__threeView.stopTool();
    }
  }
});
