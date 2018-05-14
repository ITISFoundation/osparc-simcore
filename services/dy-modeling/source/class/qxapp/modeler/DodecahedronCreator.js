qx.Class.define("qxapp.modeler.DodecahedronCreator", {
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
    __dodecahedronMaterial: null,
    __dodecahedronTemp: null,

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
        if (this.__dodecahedronTemp) {
          this.__threeView.getThreeWrapper().removeEntityFromScene(this.__dodecahedronTemp);
        }
        let dodecahedronGeometry = this.__threeView.getThreeWrapper().createDodecahedron(tempRadius);
        if (this.__dodecahedronMaterial === null) {
          this.__dodecahedronMaterial = this.__threeView.getThreeWrapper().createNewMaterial();
        }
        this.__dodecahedronTemp = this.__threeView.getThreeWrapper().createEntity(dodecahedronGeometry, this.__dodecahedronMaterial);

        this.__updatePostion(this.__dodecahedronTemp, this.__centerPoint);

        this.__threeView.getThreeWrapper().addEntityToScene(this.__dodecahedronTemp);
      }

      return true;
    },

    onMouseDown : function(event, intersects) {
      if (intersects.length > 0) {
        let intersect = intersects[0];

        if (this.__centerPoint === null) {
          this.__centerPoint = intersect.point;
          this.__nextStep = this.__steps.radius;
          return true;
        }

        if (this.__radius === null) {
          this.__radius = Math.hypot(intersect.point.x-this.__centerPoint.x, intersect.point.y-this.__centerPoint.y);
          this.__consolidateDodecahedron();
          return true;
        }
      }

      return true;
    },

    __updatePostion : function(mesh, center) {
      mesh.position.x = center.x;
      mesh.position.y = center.y;
      mesh.position.z = center.z;
    },

    __consolidateDodecahedron: function() {
      if (this.__dodecahedronTemp) {
        this.__threeView.getThreeWrapper().removeEntityFromScene(this.__dodecahedronTemp);
        this.__dodecahedronTemp = null;
      }

      let geometry = this.__threeView.getThreeWrapper().createDodecahedron(this.__radius);
      if (this.__dodecahedronMaterial === null) {
        this.__dodecahedronMaterial = this.__threeView.getThreeWrapper().createNewMaterial();
      }
      let entity = this.__threeView.getThreeWrapper().createEntity(geometry, this.__dodecahedronMaterial);
      entity.name = "Dodecahedron";

      this.__updatePostion(entity, this.__centerPoint);

      this.__threeView.addEntityToScene(entity);
      this.__threeView.stopTool();
    }
  }
});
