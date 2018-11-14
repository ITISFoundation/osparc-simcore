qx.Class.define("qxapp.modeler.CylinderCreator", {
  extend: qx.core.Object,

  construct: function(threeViewer) {
    this.__threeView = threeViewer;

    this.__steps = {
      center: 0,
      radius: 1,
      height: 2
    };
  },

  members: {
    __threeView: null,
    __steps: null,
    __nextStep: 0,
    __centerPos: null,
    __radius: null,
    __height: null,
    __planeMaterial: null,
    __circleTemp: null,
    __cylinderMaterial: null,
    __cylinderTemp: null,

    startTool: function() {
      const fixedAxe = 2;
      const fixedPos = 0;
      this.__threeView.addSnappingPlane(fixedAxe, fixedPos);
    },

    stopTool: function() {
      this.__threeView.removeSnappingPlane();
    },

    __removeTemps: function() {
      if (this.__circleTemp) {
        this.__threeView.getThreeWrapper().removeEntityFromScene(this.__circleTemp);
      }
      if (this.__cylinderTemp) {
        this.__threeView.getThreeWrapper().removeEntityFromScene(this.__cylinderTemp);
      }
    },

    onMouseHover: function(event, intersects) {
      if (intersects.length > 0) {
        let intersect = intersects[0];
        if (this.__nextStep === this.__steps.radius) {
          this.__removeTemps();

          let tempRadius = Math.hypot(intersect.point.x-this.__centerPos.x, intersect.point.y-this.__centerPos.y);
          let circleGeometry = this.__threeView.getThreeWrapper().createCylinder(tempRadius);
          if (this.__planeMaterial === null) {
            this.__planeMaterial = this.__threeView.getThreeWrapper().createNewPlaneMaterial();
          }
          this.__circleTemp = this.__threeView.getThreeWrapper().createEntity(circleGeometry, this.__planeMaterial);

          this.__updatePosition(this.__circleTemp, this.__centerPos);

          this.__threeView.getThreeWrapper().addEntityToScene(this.__circleTemp);
        } else if (this.__nextStep === this.__steps.height) {
          this.__removeTemps();

          let tempHeight = intersect.point.z - this.__centerPos.z;
          let cylinderGeometry = this.__threeView.getThreeWrapper().createCylinder(this.__radius, tempHeight);
          if (this.__cylinderMaterial === null) {
            this.__cylinderMaterial = this.__threeView.getThreeWrapper().createNewMaterial(this.__planeMaterial.color.r, this.__planeMaterial.color.g, this.__planeMaterial.color.b);
          }
          this.__cylinderTemp = this.__threeView.getThreeWrapper().createEntity(cylinderGeometry, this.__cylinderMaterial);

          this.__updatePosition(this.__cylinderTemp, this.__centerPos, tempHeight);

          this.__threeView.getThreeWrapper().addEntityToScene(this.__cylinderTemp);
        }
      }
      return true;
    },

    onMouseDown: function(event, intersects) {
      if (intersects.length > 0) {
        let intersect = intersects[0];

        if (this.__centerPos === null) {
          this.__centerPos = intersect.point;
          this.__nextStep = this.__steps.radius;
          this.__threeView.removeSnappingPlane();
          this.__threeView.addSnappingPlane(2, this.__centerPos.z);
        } else if (this.__radius === null) {
          this.__radius = Math.hypot(intersect.point.x-this.__centerPos.x, intersect.point.y-this.__centerPos.y);
          this.__nextStep = this.__steps.height;
          this.__threeView.removeSnappingPlane();
          this.__threeView.addSnappingPlane(0, this.__centerPos.x);
        } else if (this.__height === null) {
          this.__height = intersect.point.z - this.__centerPos.z;
          this._consolidateCylinder();
          this.__nextStep = 3;
        }
      }

      return true;
    },

    __updatePosition: function(mesh, center, height) {
      if (height === undefined) {
        mesh.position.x = center.x;
        mesh.position.y = center.y;
        mesh.position.z = center.z;
      } else {
        mesh.rotation.x = Math.PI / 2;
        mesh.position.x = center.x;
        mesh.position.y = center.y;
        mesh.position.z = center.z + height/2;
      }
    },

    _consolidateCylinder: function() {
      this.__removeTemps();
      if (this.__circleTemp) {
        this.__circleTemp = null;
      }
      if (this.__cylinderTemp) {
        this.__cylinderTemp = null;
      }

      let geometry = this.__threeView.getThreeWrapper().createCylinder(this.__radius, this.__height);
      if (this.__cylinderMaterial === null) {
        this.__cylinderMaterial = this.__threeView.getThreeWrapper().createNewMaterial();
      }
      let entity = this.__threeView.getThreeWrapper().createEntity(geometry, this.__cylinderMaterial);
      entity.name = "Cylinder";

      this.__updatePosition(entity, this.__centerPos, this.__height);

      this.__threeView.addEntityToScene(entity);
      this.__threeView.stopTool();
    }
  }
});
