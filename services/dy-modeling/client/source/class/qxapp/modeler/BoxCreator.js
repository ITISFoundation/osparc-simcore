qx.Class.define("qxapp.modeler.BoxCreator", {
  extend: qx.core.Object,

  construct : function(threeViewer) {
    this.__threeView = threeViewer;

    this.__steps = {
      corner0: 0,
      corner1: 1,
      corner2: 2
    };
  },

  members: {
    __threeView: null,
    __steps: null,
    __nextStep: 0,
    __corner0Pos: null,
    __corner1Pos: null,
    __corner2Pos: null,
    __planeMaterial: null,
    __squareTemp: null,
    __boxMaterial: null,
    __boxTemp: null,

    startTool: function() {
      const fixedAxe = 2;
      const fixedPos = 0;
      this.__threeView.addSnappingPlane(fixedAxe, fixedPos);
    },

    stopTool: function() {
      this.__threeView.removeSnappingPlane();
    },

    __removeTemps: function() {
      if (this.__squareTemp) {
        this.__threeView.getThreeWrapper().removeEntityFromScene(this.__squareTemp);
      }
      if (this.__boxTemp) {
        this.__threeView.getThreeWrapper().removeEntityFromScene(this.__boxTemp);
      }
    },

    onMouseHover: function(event, intersects) {
      if (intersects.length > 0) {
        let intersect = intersects[0];
        if (this.__nextStep === this.__steps.corner1) {
          this.__removeTemps();

          let squareGeometry = this.__threeView.getThreeWrapper().createBox(this.__corner0Pos, intersect.point);
          if (this.__planeMaterial === null) {
            this.__planeMaterial = this.__threeView.getThreeWrapper().createNewPlaneMaterial();
          }
          this.__squareTemp = this.__threeView.getThreeWrapper().createEntity(squareGeometry, this.__planeMaterial);

          this.__updatePosition(this.__squareTemp, this.__corner0Pos, intersect.point);

          this.__threeView.getThreeWrapper().addEntityToScene(this.__squareTemp);
        } else if (this.__nextStep === this.__steps.corner2) {
          this.__removeTemps();

          let boxGeometry = this.__threeView.getThreeWrapper().createBox(this.__corner0Pos, this.__corner1Pos, intersect.point);
          if (this.__boxMaterial === null) {
            this.__boxMaterial = this.__threeView.getThreeWrapper().createNewMaterial(this.__planeMaterial.color.r, this.__planeMaterial.color.g, this.__planeMaterial.color.b);
          }
          this.__boxTemp = this.__threeView.getThreeWrapper().createEntity(boxGeometry, this.__boxMaterial);

          this.__updatePosition(this.__boxTemp, this.__corner0Pos, this.__corner1Pos, intersect.point);

          this.__threeView.getThreeWrapper().addEntityToScene(this.__boxTemp);
        }
      }
      return true;
    },

    onMouseDown: function(event, intersects) {
      if (intersects.length > 0) {
        let intersect = intersects[0];

        if (this.__corner0Pos === null) {
          this.__corner0Pos = intersect.point;
          this.__nextStep = this.__steps.corner1;
        } else if (this.__corner1Pos === null) {
          this.__corner1Pos = intersect.point;
          this.__nextStep = this.__steps.corner2;
          this.__threeView.removeSnappingPlane();
          this.__threeView.addSnappingPlane(0, this.__corner1Pos.x);
        } else if (this.__corner2Pos === null) {
          this.__corner2Pos = intersect.point;
          this.__consolidateBox();
          this.__nextStep = 3;
        }
      }

      return true;
    },

    __updatePosition: function(mesh, p1, p2, p3) {
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

    __consolidateBox: function() {
      this.__removeTemps();
      if (this.__squareTemp) {
        this.__squareTemp = null;
      }
      if (this.__boxTemp) {
        this.__boxTemp = null;
      }

      let geometry = this.__threeView.getThreeWrapper().createBox(this.__corner0Pos, this.__corner1Pos, this.__corner2Pos);
      if (this.__boxMaterial === null) {
        this.__boxMaterial = this.__threeView.getThreeWrapper().createNewMaterial();
      }
      let entity = this.__threeView.getThreeWrapper().createEntity(geometry, this.__boxMaterial);
      entity.name = "Box";

      this.__updatePosition(entity, this.__corner0Pos, this.__corner1Pos, this.__corner2Pos);

      this.__threeView.addEntityToScene(entity);
      this.__threeView.stopTool();
    }
  }
});
