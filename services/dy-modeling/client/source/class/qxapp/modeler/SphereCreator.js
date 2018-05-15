qx.Class.define("qxapp.modeler.SphereCreator", {
  extend: qx.core.Object,

  construct: function(threeViewer) {
    this.__threeView = threeViewer;

    this.__steps = {
      centerPoint: 0,
      radius: 1
    };
  },

  members: {
    __threeView: null,
    __steps: null,
    __nextStep: 0,
    __centerPoint: null,
    __radius: null,
    __sphereMaterial: null,
    __sphereTemp: null,

    startTool: function() {
      const fixedAxe = 2;
      const fixedPos = 0;
      this.__threeView.addInvisiblePlane(fixedAxe, fixedPos);
    },

    stopTool: function() {
      this.__threeView.removeInvisiblePlane();
    },

    onMouseHover: function(event, intersects) {
      if (intersects.length > 0 && this.__nextStep === this.__steps.radius) {
        let intersect = intersects[0];
        let tempRadius = Math.hypot(intersect.point.x-this.__centerPoint.x, intersect.point.y-this.__centerPoint.y);
        if (this.__sphereTemp) {
          this.__threeView.getThreeWrapper().removeEntityFromScene(this.__sphereTemp);
        }
        let sphereGeometry = this.__threeView.getThreeWrapper().createSphere(tempRadius);
        if (this.__sphereMaterial === null) {
          this.__sphereMaterial = this.__threeView.getThreeWrapper().createNewMaterial();
        }
        this.__sphereTemp = this.__threeView.getThreeWrapper().createEntity(sphereGeometry, this.__sphereMaterial);

        this.__updatePostion(this.__sphereTemp, this.__centerPoint);

        this.__threeView.getThreeWrapper().addEntityToScene(this.__sphereTemp);
      }

      return true;
    },

    onMouseDown: function(event, intersects) {
      if (intersects.length > 0) {
        let intersect = intersects[0];

        if (this.__centerPoint === null) {
          this.__centerPoint = intersect.point;
          this.__nextStep = this.__steps.radius;
          return true;
        }

        if (this.__radius === null) {
          this.__radius = Math.hypot(intersect.point.x-this.__centerPoint.x, intersect.point.y-this.__centerPoint.y);
          this.__consolidateSphere();
          return true;
        }
      }

      return true;
    },

    __updatePostion: function(mesh, center) {
      mesh.position.x = center.x;
      mesh.position.y = center.y;
      mesh.position.z = center.z;
    },

    __consolidateSphere: function() {
      if (this.__sphereTemp) {
        this.__threeView.getThreeWrapper().removeEntityFromScene(this.__sphereTemp);
        this.__sphereTemp = null;
      }

      let geometry = this.__threeView.getThreeWrapper().createSphere(this.__radius);
      if (this.__sphereMaterial === null) {
        this.__sphereMaterial = this.__threeView.getThreeWrapper().createNewMaterial();
      }
      let entity = this.__threeView.getThreeWrapper().createEntity(geometry, this.__sphereMaterial);
      entity.name = "Sphere";

      this.__updatePostion(entity, this.__centerPoint);

      this.__threeView.addEntityToScene(entity);
      this.__threeView.stopTool();
    }
  }
});
